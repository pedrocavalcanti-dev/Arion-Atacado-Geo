"""Queue snapshot synchronization through the dedicated read-only OTRS client."""
from collections import Counter
import logging
import re
import time

from django.db import transaction
from django.utils import timezone

from aplicativos.integracoes.models import (
    CMDBLinkMirror, OTRSStateMapping, OTRSTicket, OTRSTicketConfigItem,
)

from .sync_common import clean, integer_or_none, normalized_name, source_datetime

logger = logging.getLogger(__name__)
IDENTIFIER = re.compile(r"^[A-Za-z0-9_$]+$")
BUSINESS_STATES = {
    "em atendimento": OTRSStateMapping.BusinessStatus.OPEN,
    "pendente": OTRSStateMapping.BusinessStatus.PENDING,
    "resolvido": OTRSStateMapping.BusinessStatus.RESOLVED,
    "closed successful": OTRSStateMapping.BusinessStatus.CLOSED,
    "encerrado com viabilidade": OTRSStateMapping.BusinessStatus.CLOSED,
    "cancelado": OTRSStateMapping.BusinessStatus.CANCELED,
}
OPEN_STATUSES = {OTRSStateMapping.BusinessStatus.OPEN, OTRSStateMapping.BusinessStatus.PENDING}


def _val(row, key, default=None):
    return row.get(key, row.get(key.lower(), default)) if isinstance(row, dict) else default


def _number(value):
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


class OTRSSyncService:
    TICKET_TABLE = "ticket"
    QUEUE_TABLE = "queue"
    RELATION_TABLE = "link_relation"

    def __init__(self, client, *, progress=lambda _: None):
        self.client = client
        self.progress = progress
        self.tables = set()
        self.columns = {}

    def _discover(self):
        rows = self.client.get_all_columns()
        self.tables = {str(_val(row, "TABLE_NAME")) for row in rows if _val(row, "TABLE_NAME")}
        for row in rows:
            table = str(_val(row, "TABLE_NAME") or "")
            column = str(_val(row, "COLUMN_NAME") or "")
            self.columns.setdefault(table.casefold(), set()).add(column)
        required = (self.TICKET_TABLE, self.QUEUE_TABLE, "ticket_state", "ticket_state_type", "ticket_priority", "ticket_type", "service", "sla", self.RELATION_TABLE, "link_object", "link_type", "link_state")
        missing = [name for name in required if name.casefold() not in self.columns]
        if missing:
            raise ValueError("Schema OTRS incompleto para sync: " + ", ".join(missing))

    def _table(self, name):
        actual = next((table for table in self.tables if table.casefold() == name.casefold()), None)
        if not actual or not IDENTIFIER.fullmatch(actual):
            raise ValueError("Tabela OTRS fora do allowlist do schema.")
        return f"`{actual}`"

    def _column(self, table, name, *, required=False):
        columns = self.columns.get(table.casefold(), set())
        actual = next((column for column in columns if column.casefold() == name.casefold()), None)
        if required and not actual:
            raise ValueError(f"Coluna necessária não encontrada: {table}.{name}.")
        if actual and not IDENTIFIER.fullmatch(actual):
            raise ValueError("Coluna OTRS fora do allowlist do schema.")
        return f"`{actual}`" if actual else None

    def _select(self, table, mapping, *, where="", params=()):
        projection = []
        for alias, column in mapping:
            quoted = self._column(table, column)
            if quoted:
                projection.append(f"{quoted} AS `{alias}`")
        if not projection:
            raise ValueError(f"Nenhuma coluna segura disponível em {table}.")
        sql = f"SELECT {', '.join(projection)} FROM {self._table(table)}"
        if where:
            sql += " WHERE " + where
        return self.client.execute_select(sql, params)

    def _dimension(self, table, *, with_type=False):
        mapping = [("id", "id"), ("name", "name")]
        if with_type:
            mapping.append(("type_id", "type_id"))
        return self._select(table, mapping)

    @staticmethod
    def _dimension_map(rows):
        return {_number(_val(row, "id")): clean(_val(row, "name")) for row in rows if _number(_val(row, "id")) is not None}

    def _queue(self, queue_name):
        rows = self._select("queue", (("id", "id"), ("name", "name")), where=f"{self._column('queue', 'name', required=True)} = %s", params=(queue_name,))
        exact = [row for row in rows if clean(_val(row, "name")) == queue_name]
        if len(exact) != 1:
            raise ValueError(f"A fila exata '{queue_name}' não foi encontrada de forma única.")
        return _number(_val(exact[0], "id")), clean(_val(exact[0], "name"))

    def _tickets(self, queue_id, *, changed_since=None, known_ids=()):
        fields = (
            ("id", "id", True), ("tn", "tn", True), ("title", "title", False),
            ("queue_id", "queue_id", True), ("state_id", "ticket_state_id", True),
            ("priority_id", "ticket_priority_id", False), ("type_id", "type_id", False),
            ("service_id", "service_id", False), ("sla_id", "sla_id", False),
            ("responsible_user_id", "responsible_user_id", False), ("customer_id", "customer_id", False),
            ("timeout", "timeout", False), ("until_time", "until_time", False),
            ("escalation_time", "escalation_time", False), ("escalation_update_time", "escalation_update_time", False),
            ("escalation_response_time", "escalation_response_time", False), ("escalation_solution_time", "escalation_solution_time", False),
            ("create_time", "create_time", False), ("change_time", "change_time", False),
        )
        selected = []
        for alias, column, required in fields:
            quoted = self._column("ticket", column, required=required)
            if quoted:
                selected.append(f"{quoted} AS `{alias}`")
        queue_column = self._column("ticket", "queue_id", required=True)
        where = f"{queue_column} = %s"
        params = [queue_id]
        if changed_since is not None:
            change_column = self._column("ticket", "change_time", required=True)
            id_column = self._column("ticket", "id", required=True)
            known_ids = tuple(known_ids)
            marks = ",".join(["%s"] * len(known_ids)) or "NULL"
            where = f"(({queue_column} = %s) OR ({id_column} IN ({marks}))) AND {change_column} >= %s"
            params = [queue_id, *known_ids, changed_since]
        sql = f"SELECT {', '.join(selected)} FROM {self._table('ticket')} WHERE {where}"
        rows = self.client.execute_select(sql, tuple(params))
        if any(_number(_val(row, "id")) is None or not clean(_val(row, "tn")) for row in rows):
            raise ValueError("Snapshot de ticket contém identificador ou número vazio.")
        ids = [str(_val(row, "id")) for row in rows]
        numbers = [clean(_val(row, "tn")) for row in rows]
        if len(set(ids)) != len(ids) or len(set(numbers)) != len(numbers):
            raise ValueError("IDs/números de ticket duplicados no snapshot; reconciliação cancelada.")
        return rows

    def _relation_ids(self, table, names):
        rows = self._select(table, (("id", "id"), ("name", "name")))
        matches = [_number(_val(row, "id")) for row in rows if clean(_val(row, "name")) in names]
        if len(matches) != 1:
            raise ValueError(f"Valores OTRS esperados não identificados em {table}.")
        return matches[0]

    def _object_ids(self):
        rows = self._select("link_object", (("id", "id"), ("name", "name")))
        found = {}
        for row in rows:
            name = clean(_val(row, "name"))
            if name in {"Ticket", "ITSMConfigItem"}:
                found[name] = _number(_val(row, "id"))
        if not found.get("Ticket") or not found.get("ITSMConfigItem"):
            raise ValueError("Objetos OTRS Ticket/ITSMConfigItem não foram resolvidos por nome.")
        return found

    def _relations(self, ticket_rows, objects, relation_type_id, relation_state_id):
        ticket_ids = [str(_val(row, "id")) for row in ticket_rows]
        if not ticket_ids:
            return []
        table = "link_relation"
        cols = (("source_object_id", "source_object_id"), ("source_key", "source_key"), ("target_object_id", "target_object_id"), ("target_key", "target_key"), ("type_id", "type_id"), ("state_id", "state_id"), ("create_time", "create_time"))
        projection = []
        for alias, field in cols:
            quoted = self._column(table, field)
            if quoted:
                projection.append(f"{quoted} AS `{alias}`")
        source_obj = self._column(table, "source_object_id", required=True)
        source_key = self._column(table, "source_key", required=True)
        target_obj = self._column(table, "target_object_id", required=True)
        target_key = self._column(table, "target_key", required=True)
        result = []
        for offset in range(0, len(ticket_ids), 400):
            batch = ticket_ids[offset:offset + 400]
            marks = ",".join(["%s"] * len(batch))
            sql = (f"SELECT {', '.join(projection)} FROM {self._table(table)} WHERE "
                   f"({source_obj} = %s AND {source_key} IN ({marks})) OR "
                   f"({target_obj} = %s AND {target_key} IN ({marks}))")
            rows = self.client.execute_select(sql, (objects["Ticket"], *batch, objects["Ticket"], *batch))
            for row in rows:
                if _number(_val(row, "type_id")) != relation_type_id or _number(_val(row, "state_id")) != relation_state_id:
                    continue
                source_object = _number(_val(row, "source_object_id"))
                target_object = _number(_val(row, "target_object_id"))
                if source_object == objects["ITSMConfigItem"] and target_object == objects["Ticket"]:
                    ci_id, ticket_id = clean(_val(row, "source_key")), _number(_val(row, "target_key"))
                elif source_object == objects["Ticket"] and target_object == objects["ITSMConfigItem"]:
                    ticket_id, ci_id = _number(_val(row, "source_key")), clean(_val(row, "target_key"))
                else:
                    continue
                if ticket_id is not None and ci_id:
                    result.append({"ticket_id": ticket_id, "config_item_id": ci_id, "relation_type": "DependsOn", "relation_state": "Valid", "source_created_at": source_datetime(_val(row, "create_time"))})
        keys = [(row["ticket_id"], row["config_item_id"], row["relation_type"]) for row in result]
        if len(keys) != len(set(keys)):
            raise ValueError("Relações OTRS duplicadas no snapshot; reconciliação cancelada.")
        return result

    @staticmethod
    def _state_status(name):
        return BUSINESS_STATES.get(normalized_name(name), OTRSStateMapping.BusinessStatus.UNKNOWN)

    def _normalize_tickets(self, ticket_rows, queue_id, queue_name, dimensions, state_type_map, now):
        statuses = Counter()
        mappings = {}
        warnings = []
        for row in dimensions["states"]:
            state_id = _number(_val(row, "id"))
            if state_id is None:
                continue
            name = clean(_val(row, "name"))
            state_type = state_type_map.get(_number(_val(row, "type_id")), "")
            status = self._state_status(name)
            mappings[state_id] = {"external_state_id": state_id, "external_name": name, "external_type": state_type, "business_status": status, "is_configured": status != OTRSStateMapping.BusinessStatus.UNKNOWN, "source_last_seen_at": now}
        normalized = []
        dimension_maps = {key: self._dimension_map(dimensions[key]) for key in ("priorities", "types", "services", "slas")}
        for row in ticket_rows:
            state_id = _number(_val(row, "state_id"))
            state_map = mappings.get(state_id)
            state_name = state_map["external_name"] if state_map else ""
            state_type = state_map["external_type"] if state_map else ""
            status = state_map["business_status"] if state_map else OTRSStateMapping.BusinessStatus.UNKNOWN
            if status == OTRSStateMapping.BusinessStatus.UNKNOWN:
                warnings.append(f"Estado sem mapeamento explícito: {state_name or state_id}")
            statuses[status] += 1
            def dim_value(field, map_key):
                identifier = _number(_val(row, field))
                return identifier, dimension_maps[map_key].get(identifier, "")
            priority_id, priority_name = dim_value("priority_id", "priorities")
            type_id, type_name = dim_value("type_id", "types")
            service_id, service_name = dim_value("service_id", "services")
            sla_id, sla_name = dim_value("sla_id", "slas")
            normalized.append({
                "external_id": _number(_val(row, "id")), "ticket_number": clean(_val(row, "tn"), 80),
                "title": clean(_val(row, "title"), 500), "queue_external_id": _number(_val(row, "queue_id")) or queue_id, "queue_name": queue_name,
                "external_state_id": state_id or 0, "external_state_name": state_name, "external_state_type": state_type,
                "business_status": status, "is_business_open": status in OPEN_STATUSES,
                "external_priority_id": priority_id, "priority_name": priority_name,
                "external_type_id": type_id, "type_name": type_name,
                "external_service_id": service_id, "service_name": service_name,
                "external_sla_id": sla_id, "sla_name": sla_name,
                "responsible_user_id": _number(_val(row, "responsible_user_id")),
                "customer_id": clean(_val(row, "customer_id"), 250),
                "timeout": _number(_val(row, "timeout")), "until_time": _number(_val(row, "until_time")),
                "escalation_time": _number(_val(row, "escalation_time")),
                "escalation_update_time": _number(_val(row, "escalation_update_time")),
                "escalation_response_time": _number(_val(row, "escalation_response_time")),
                "escalation_solution_time": _number(_val(row, "escalation_solution_time")),
                "source_created_at": source_datetime(_val(row, "create_time")),
                "source_changed_at": source_datetime(_val(row, "change_time")),
                "is_present_in_queue": (_number(_val(row, "queue_id")) == queue_id),
            })
        # Log only state names and counts; never titles or customer details.
        for warning in sorted(set(warnings)):
            logger.warning("OTRS sync: %s", warning)
        return normalized, mappings, statuses, sorted(set(warnings))

    @staticmethod
    def _upsert_dimension(model, rows, *, apply):
        existing = {obj.external_state_id: obj for obj in model.objects.all()}
        fields = ("external_name", "external_type", "business_status", "is_configured", "source_last_seen_at")
        create, update, created, updated, unchanged = [], [], 0, 0, 0
        for row in rows.values():
            current = existing.get(row["external_state_id"])
            if current is None:
                create.append(model(**row))
                created += 1
            else:
                changed = any(getattr(current, field) != row[field] for field in fields[:-1])
                if changed:
                    updated += 1
                else:
                    unchanged += 1
                for key, value in row.items():
                    setattr(current, key, value)
                update.append(current)
        if apply:
            model.objects.bulk_create(create, batch_size=500)
            model.objects.bulk_update(update, fields=fields, batch_size=500)
        return {"found": len(rows), "processed": len(rows), "created": created, "updated": updated, "unchanged": unchanged, "failed": 0}

    @staticmethod
    def _upsert_tickets(rows, *, now, apply, reconcile=True):
        existing = {obj.external_id: obj for obj in OTRSTicket.objects.all()}
        fields = tuple(rows[0].keys()) if rows else ()
        create, update, created, updated, unchanged = [], [], 0, 0, 0
        source_ids = set()
        for row in rows:
            source_ids.add(row["external_id"])
            values = {**row, "source_last_seen_at": now, "source_synced_at": now, "is_present_in_queue": row.get("is_present_in_queue", True)}
            current = existing.get(row["external_id"])
            if current is None:
                create.append(OTRSTicket(**values))
                created += 1
                continue
            changed = any(getattr(current, field) != row[field] for field in fields) or not current.is_present_in_queue
            if changed:
                updated += 1
            else:
                unchanged += 1
            for key, value in values.items():
                setattr(current, key, value)
            update.append(current)
        stale_ids = [obj.pk for obj in existing.values() if reconcile and obj.is_present_in_queue and obj.external_id not in source_ids]
        if apply:
            OTRSTicket.objects.bulk_create(create, batch_size=500)
            OTRSTicket.objects.bulk_update(update, fields=[*fields, "source_last_seen_at", "source_synced_at", "is_present_in_queue"], batch_size=500)
            if stale_ids:
                OTRSTicket.objects.filter(pk__in=stale_ids).update(is_present_in_queue=False)
        return {"found": len(rows), "processed": len(rows), "created": created, "updated": updated, "unchanged": unchanged, "stale": len(stale_ids), "failed": 0}

    @staticmethod
    def _upsert_relations(relations, *, ticket_map, now, apply, affected_ticket_ids=None):
        tickets_by_external = {ticket.external_id: ticket for ticket in ticket_map.values()}
        links_by_ci = CMDBLinkMirror.objects.in_bulk(field_name="source_config_item_id")
        existing = {
            (row.ticket_id, row.config_item_id, row.relation_type): row
            for row in OTRSTicketConfigItem.objects.filter(is_present_in_source=True).filter(
                **({} if affected_ticket_ids is None else {"ticket__external_id__in": affected_ticket_ids})
            )
        }
        create, update, created, updated, unchanged = [], [], 0, 0, 0
        seen = set()
        fields = ("ticket_id", "config_item_id", "cmdb_link_id", "relation_type", "relation_state", "source_created_at", "source_last_seen_at", "source_synced_at", "is_present_in_source")
        for relation in relations:
            ticket = tickets_by_external.get(relation["ticket_id"])
            if not ticket:
                raise ValueError("Relação recebida para ticket fora da fila; reconciliação cancelada.")
            link = links_by_ci.get(relation["config_item_id"])
            values = {
                "ticket_id": ticket.pk, "config_item_id": relation["config_item_id"],
                "cmdb_link_id": link.pk if link else None, "relation_type": relation["relation_type"],
                "relation_state": relation["relation_state"], "source_created_at": relation["source_created_at"],
                "source_last_seen_at": now, "source_synced_at": now, "is_present_in_source": True,
            }
            key = (ticket.pk, relation["config_item_id"], relation["relation_type"])
            seen.add(key)
            current = existing.get(key)
            if current is None:
                create.append(OTRSTicketConfigItem(**values))
                created += 1
            else:
                changed = any(getattr(current, field) != values[field] for field in fields[:-3]) or not current.is_present_in_source
                if changed:
                    updated += 1
                else:
                    unchanged += 1
                for name, value in values.items():
                    setattr(current, name, value)
                update.append(current)
        stale_ids = [row.pk for key, row in existing.items() if row.is_present_in_source and key not in seen]
        if apply:
            OTRSTicketConfigItem.objects.bulk_create(create, batch_size=500)
            OTRSTicketConfigItem.objects.bulk_update(update, fields=fields, batch_size=500)
            if stale_ids:
                OTRSTicketConfigItem.objects.filter(pk__in=stale_ids).update(is_present_in_source=False)
        return {"found": len(relations), "processed": len(relations), "created": created, "updated": updated, "unchanged": unchanged, "stale": len(stale_ids), "failed": 0, "unresolved_link": sum(1 for row in relations if row["config_item_id"] not in links_by_ci)}

    def run(self, queue_name="NOC - ATACADO", *, apply=False, changed_since=None, safety_window=120):
        started = time.perf_counter()
        queries_before = getattr(self.client, "select_queries_count", 0)
        self._discover()
        queue_id, resolved_queue = self._queue(queue_name)
        if queue_id != 107:
            self.progress(f"[OTRS] Aviso: fila resolvida por nome com id={queue_id}; estudo anterior observou 107.")
        self.progress(f"[OTRS] Fila {resolved_queue} encontrada: id={queue_id}.")

        dimensions = {
            "states": self._dimension("ticket_state", with_type=True),
            "priorities": self._dimension("ticket_priority"),
            "types": self._dimension("ticket_type"),
            "services": self._dimension("service"),
            "slas": self._dimension("sla"),
        }
        type_rows = self._dimension("ticket_state_type")
        state_type_map = self._dimension_map(type_rows)
        now = timezone.now()
        known_ids = tuple(OTRSTicket.objects.values_list("external_id", flat=True)) if changed_since is not None else ()
        if changed_since is not None:
            from datetime import timedelta
            changed_since -= timedelta(seconds=safety_window)
        ticket_source_rows = self._tickets(queue_id, changed_since=changed_since, known_ids=known_ids)
        self.progress(f"[OTRS] Tickets atuais encontrados: {len(ticket_source_rows)}.")
        tickets, state_mappings, status_counts, warnings = self._normalize_tickets(ticket_source_rows, queue_id, resolved_queue, dimensions, state_type_map, now)
        objects = self._object_ids()
        relation_type_id = self._relation_ids("link_type", {"DependsOn"})
        relation_state_id = self._relation_ids("link_state", {"Valid"})
        relation_rows = self._relations(ticket_source_rows, objects, relation_type_id, relation_state_id)
        self.progress(f"[OTRS] Relações válidas ticket–ConfigItem: {len(relation_rows)}.")
        ticket_ci_counts = Counter(row["ticket_id"] for row in relation_rows)
        ci_ticket_counts = Counter(row["config_item_id"] for row in relation_rows)
        local_ci_ids = set(CMDBLinkMirror.objects.values_list("source_config_item_id", flat=True))
        relation_stats = {
            "tickets_with_ci": len(ticket_ci_counts),
            "tickets_without_ci": max(0, len(tickets) - len(ticket_ci_counts)),
            "tickets_one_ci": sum(1 for count in ticket_ci_counts.values() if count == 1),
            "tickets_multiple_ci": sum(1 for count in ticket_ci_counts.values() if count > 1),
            "unique_config_items": len(ci_ticket_counts),
            "configitems_multiple_tickets": sum(1 for count in ci_ticket_counts.values() if count > 1),
            "resolved_local_links": sum(1 for row in relation_rows if row["config_item_id"] in local_ci_ids),
            "unresolved_local_links": sum(1 for row in relation_rows if row["config_item_id"] not in local_ci_ids),
        }

        # Validate exact TN uniqueness before any local reconciliation.
        ticket_counts = Counter(row["ticket_number"] for row in tickets)
        if any(count > 1 for count in ticket_counts.values()):
            raise ValueError("Números de ticket duplicados; reconciliação cancelada.")
        number_owners = {ticket.ticket_number: ticket.external_id for ticket in OTRSTicket.objects.filter(ticket_number__in=[row["ticket_number"] for row in tickets])}
        if any(number_owners.get(row["ticket_number"], row["external_id"]) != row["external_id"] for row in tickets):
            raise ValueError("TN já pertence a outro ID externo local; reconciliação cancelada.")
        with transaction.atomic() if apply else _NullContext():
            mapping_counts = self._upsert_dimension(OTRSStateMapping, state_mappings, apply=apply)
            ticket_counts_summary = self._upsert_tickets(tickets, now=now, apply=apply, reconcile=changed_since is None)
            if apply:
                ticket_map = {row.external_id: row for row in OTRSTicket.objects.filter(external_id__in=[row["external_id"] for row in tickets])}
            else:
                existing_tickets = {row.external_id: row for row in OTRSTicket.objects.filter(external_id__in=[item["external_id"] for item in tickets])}
                ticket_map = {
                    item["external_id"]: existing_tickets.get(item["external_id"]) or OTRSTicket(external_id=item["external_id"], **{key: value for key, value in item.items() if key != "external_id"})
                    for item in tickets
                }
            relation_counts_summary = self._upsert_relations(
                relation_rows, ticket_map=ticket_map, now=now, apply=apply,
                affected_ticket_ids=[item["external_id"] for item in tickets] if changed_since is not None else None,
            )

        status_counts = {key: status_counts.get(key, 0) for key in OTRSStateMapping.BusinessStatus.values}
        result = {
            "status": "APPLIED" if apply else "DRY_RUN", "queue": {"name": resolved_queue, "id": queue_id},
            "tickets": ticket_counts_summary, "relations": relation_counts_summary, "state_mappings": mapping_counts,
            "relation_stats": relation_stats,
            "business_status": status_counts, "business_open": status_counts["OPEN"] + status_counts["PENDING"],
            "cursor": max((item["source_changed_at"] for item in tickets if item.get("source_changed_at")), default=None),
            "warnings": warnings, "performance": {"duration_ms": int((time.perf_counter() - started) * 1000), "select_queries": getattr(self.client, "select_queries_count", queries_before) - queries_before, "ticket_query_rows": len(ticket_source_rows), "relation_rows": len(relation_rows), "relation_batches": (len(ticket_source_rows) + 399) // 400},
        }
        return result


class _NullContext:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False
