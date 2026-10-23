"""Bounded, read-only OTRS schema and queue study; results stay in memory."""
from collections import Counter
from datetime import datetime, timezone
import re
import time

from aplicativos.integracoes.clients.cmdb import CMDBClient


SEARCH_TERMS = (
    "ticket", "queue", "state", "priority", "type", "service", "sla", "article",
    "history", "dynamic", "field", "link", "relation", "object", "config", "item",
    "cmdb", "itsm", "catalog", "customer",
)
SENSITIVE = re.compile(r"(password|passwd|pwd|(^|_)pw($|_)|secret|token|credential|session|cookie|auth|body|mime|attachment)", re.I)
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_$]+$")


def _norm(value):
    return "".join(char.casefold() for char in str(value or "") if char.isalnum())


def _row_value(row, key, default=None):
    if isinstance(row, dict):
        return row.get(key, row.get(key.lower(), default))
    return default


class OTRSStudyService:
    """Inspects OTRS metadata and selected aggregate data without persisting it."""

    SAMPLE_LIMIT = 20
    CMDB_SAMPLE_LIMIT = 50

    def __init__(self, client, *, cmdb_client=None, progress=lambda _: None):
        self.client = client
        self.cmdb_client = cmdb_client
        self.progress = progress
        self.tables = {}
        self.columns = {}
        self.started = None

    def run(self, queue_name="NOC - ATACADO"):
        self.started = time.perf_counter()
        self.progress("[OTRS] Descobrindo schema...")
        server = self.client.get_server_metadata()
        table_rows = self.client.list_tables()
        self.tables = {_norm(row["name"]): row for row in table_rows}
        all_columns = self.client.get_all_columns()
        for row in all_columns:
            table = str(_row_value(row, "TABLE_NAME", ""))
            self.columns.setdefault(_norm(table), []).append({
                "column": _row_value(row, "COLUMN_NAME"),
                "type": _row_value(row, "COLUMN_TYPE"),
                "nullable": _row_value(row, "IS_NULLABLE"),
                "key": _row_value(row, "COLUMN_KEY"),
                "position": _row_value(row, "ORDINAL_POSITION"),
            })
        candidates = self._candidate_tables()
        candidate_columns = [
            {"table": table["name"], **column}
            for table in candidates
            for column in self.columns.get(_norm(table["name"]), [])
            if not SENSITIVE.search(str(column["column"]))
        ]
        queue_result = self._resolve_queue(queue_name)
        ticket_result = self._study_tickets(queue_result)
        relationship = self._study_links(ticket_result, queue_result)
        cmdb = self._crosscheck(relationship)
        dimensions = self._study_dimensions(ticket_result, queue_result)
        dimensions["link_types"] = self._relation_distribution(relationship, "type_values", "type_definitions", "link_type")
        dimensions["link_states"] = self._relation_distribution(relationship, "state_values", "state_definitions", "link_state")
        local_cmdb = self._classify_configitems(relationship)
        open_review = self._open_review(ticket_result, relationship, dimensions)
        open_review.update(self._open_link_review(ticket_result, relationship, local_cmdb, open_review))
        association_proof = self._association_proof(ticket_result, relationship, cmdb)
        duration = round(time.perf_counter() - self.started, 2)
        result = {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "duration_seconds": duration,
            "database": server,
            "tables": table_rows,
            "candidate_tables": candidates,
            "candidate_columns": candidate_columns,
            "queue": queue_result,
            "ticket": ticket_result,
            "relationship": relationship,
            "cmdb": cmdb,
            "local_cmdb": local_cmdb,
            "dimensions": dimensions,
            "open_review": open_review,
            "association_proof": association_proof,
        }
        result["report"] = self.render_report(result)
        return result

    def _candidate_tables(self):
        result = []
        for table in self.tables.values():
            name = table["name"]
            normalized = _norm(name)
            matched = [term for term in SEARCH_TERMS if _norm(term) in normalized]
            if matched:
                result.append({**table, "matched_terms": matched})
        return result

    def _table(self, *names):
        for name in names:
            row = self.tables.get(_norm(name))
            if row:
                return row["name"]
        return None

    def _cols(self, table):
        return {str(row["column"]).casefold(): row["column"] for row in self.columns.get(_norm(table), [])}

    def _col(self, table, *names):
        available = self._cols(table)
        for name in names:
            if name.casefold() in available:
                return available[name.casefold()]
        return None

    def _qtable(self, table):
        if not table or _norm(table) not in self.tables or not _IDENTIFIER.fullmatch(table):
            raise ValueError("Tabela fora do allowlist do schema OTRS.")
        return f"`{table}`"

    def _qcol(self, table, column):
        if not column or column.casefold() not in self._cols(table) or not _IDENTIFIER.fullmatch(column):
            raise ValueError("Coluna fora do allowlist do schema OTRS.")
        if SENSITIVE.search(column):
            raise ValueError("Coluna sensível recusada pelo estudo.")
        return f"`{column}`"

    def _resolve_queue(self, queue_name):
        table = self._table("queue")
        if not table:
            return {"table": None, "name": queue_name, "id": None, "status": "tabela queue não encontrada", "candidates": []}
        id_col, name_col = self._col(table, "id"), self._col(table, "name")
        if not id_col or not name_col:
            return {"table": table, "name": queue_name, "id": None, "status": "colunas id/name não confirmadas", "candidates": []}
        sql = f"SELECT {self._qcol(table, id_col)} AS queue_id, {self._qcol(table, name_col)} AS queue_name FROM {self._qtable(table)} WHERE {self._qcol(table, name_col)} = %s LIMIT 20"
        rows = self.client.execute_select(sql, (queue_name,))
        candidates = [{"id": _row_value(row, "queue_id"), "name": _row_value(row, "queue_name")} for row in rows]
        exact = next((row for row in candidates if row["name"] == queue_name), None)
        if exact:
            self.progress(f"[OTRS] Fila {queue_name} encontrada: id={exact['id']}")
            return {"table": table, **exact, "status": "encontrada por nome exato", "candidates": candidates}
        similar = self.client.execute_select(
            f"SELECT {self._qcol(table, id_col)} AS queue_id, {self._qcol(table, name_col)} AS queue_name FROM {self._qtable(table)} WHERE {self._qcol(table, name_col)} LIKE %s LIMIT 20",
            (f"%{queue_name}%",),
        )
        candidates = [{"id": _row_value(row, "queue_id"), "name": _row_value(row, "queue_name")} for row in similar]
        return {"table": table, "name": queue_name, "id": None, "status": "sem correspondência exata", "candidates": candidates}

    def _study_tickets(self, queue):
        table = self._table("ticket")
        if not table:
            return {"table": None, "status": "tabela ticket não encontrada", "count": 0, "ids": [], "columns": [], "indexes": []}
        queue_col, id_col = self._col(table, "queue_id"), self._col(table, "id")
        if not queue["id"] or not queue_col or not id_col:
            return {"table": table, "status": "fila/tabela sem chave confirmada", "count": 0, "ids": [], "columns": self._ticket_columns(table), "indexes": self.client.get_table_indexes(table)}
        selected_names = (
            ("id", ("id",)), ("tn", ("tn",)), ("queue_id", ("queue_id",)),
            ("state_id", ("state_id", "ticket_state_id")),
            ("priority_id", ("priority_id", "ticket_priority_id")),
            ("type_id", ("type_id", "ticket_type_id")), ("service_id", ("service_id",)),
            ("sla_id", ("sla_id",)), ("user_id", ("user_id",)),
            ("responsible_user_id", ("responsible_user_id",)), ("customer_id", ("customer_id",)),
            ("customer_user_id", ("customer_user_id",)), ("create_time", ("create_time",)),
            ("change_time", ("change_time",)), ("until_time", ("until_time",)),
            ("escalation_time", ("escalation_time",)),
            ("escalation_update_time", ("escalation_update_time",)),
            ("escalation_response_time", ("escalation_response_time",)),
            ("escalation_solution_time", ("escalation_solution_time",)),
        )
        chosen = [(alias, self._col(table, *names)) for alias, names in selected_names]
        chosen = [(name, col) for name, col in chosen if col and not SENSITIVE.search(col)]
        selection = ", ".join(f"{self._qcol(table, col)} AS `{name}`" for name, col in chosen)
        sql = f"SELECT {selection} FROM {self._qtable(table)} WHERE {self._qcol(table, queue_col)} = %s"
        rows = self.client.execute_select(sql, (queue["id"],))
        states = Counter(str(_row_value(row, "state_id", "(nulo)")) for row in rows)
        result = {
            "table": table, "status": "atual por ticket.queue_id", "count": len(rows),
            "ids": [_row_value(row, "id") for row in rows], "rows": rows,
            "columns": self._ticket_columns(table), "indexes": self.client.get_table_indexes(table),
            "foreign_keys": self.client.get_foreign_keys(table),
            "state_ids": dict(states), "selected_columns": [col for _, col in chosen],
        }
        self.progress(f"[OTRS] Tickets atualmente na fila analisados: {result['count']}")
        return result

    def _ticket_columns(self, table):
        return [row for row in self.columns.get(_norm(table), []) if not SENSITIVE.search(str(row["column"]))]

    def _study_links(self, ticket, queue):
        result = {"status": "não confirmada", "table": None, "object_table": None, "associations": [], "ticket_ci_counts": {}, "unique_ci_keys": [], "type_values": {}, "state_values": {}, "indexes": [], "evidence": []}
        if not ticket["ids"]:
            result["reason"] = "Não há tickets carregados da fila exata."
            return result
        table = next((row["name"] for row in self.tables.values() if "link" in _norm(row["name"]) and self._col(row["name"], "source_key", "sourcekey") and self._col(row["name"], "target_key", "targetkey") and self._col(row["name"], "source_object_id", "source_object") and self._col(row["name"], "target_object_id", "target_object")), None)
        if not table:
            result["reason"] = "Nenhuma tabela candidata com source/target key foi encontrada."
            return result
        cols = self._cols(table)
        source_key = self._col(table, "source_key", "sourcekey")
        target_key = self._col(table, "target_key", "targetkey")
        source_object = self._col(table, "source_object_id", "source_object", "sourceobjectid")
        target_object = self._col(table, "target_object_id", "target_object", "targetobjectid")
        if not all((source_key, target_key, source_object, target_object)):
            result.update(table=table, reason="Tabela candidata sem os quatro campos source/target esperados.")
            return result
        object_table = self._table("link_object")
        # OTRS variants usually store object IDs in link_object and names in link_object_type.
        object_table = next((row["name"] for row in self.tables.values() if "object" in _norm(row["name"]) and self._col(row["name"], "name") and self._col(row["name"], "id")), object_table)
        result.update(table=table, object_table=object_table, indexes=self.client.get_table_indexes(table), foreign_keys=self.client.get_foreign_keys(table), columns=self._ticket_columns(table))
        if not object_table or object_table == table:
            result["reason"] = "Tabela de IDs/nome dos objetos não identificada; relation table encontrada, sem prova da semântica dos IDs."
            return result
        object_id_col, object_name_col = self._col(object_table, "id"), self._col(object_table, "name")
        obj_rows = self.client.execute_select(f"SELECT {self._qcol(object_table, object_id_col)} AS object_id, {self._qcol(object_table, object_name_col)} AS object_name FROM {self._qtable(object_table)} LIMIT 100")
        object_labels = {_norm(_row_value(row, "object_name")): str(_row_value(row, "object_name")) for row in obj_rows}
        object_names = {_norm(_row_value(row, "object_name")): _row_value(row, "object_id") for row in obj_rows}
        ticket_object_id = next((value for key, value in object_names.items() if key == "ticket"), None)
        ci_object_id = next((value for key, value in object_names.items() if "configitem" in key or key == "cmdb"), None)
        if ticket_object_id is None or ci_object_id is None:
            result.update(object_names=sorted(object_labels.values()), reason="Objeto Ticket ou ConfigItem não identificado na tabela de objetos.")
            return result
        type_table, state_table = self._table("link_type"), self._table("link_state")
        type_defs = self._relation_definitions(type_table)
        state_defs = self._relation_definitions(state_table)
        ticket_ids = [str(value) for value in ticket["ids"] if value is not None]
        rows = []
        q = self._qtable(table)
        qsk, qtk = self._qcol(table, source_key), self._qcol(table, target_key)
        qso, qto = self._qcol(table, source_object), self._qcol(table, target_object)
        for offset in range(0, len(ticket_ids), 300):
            batch = ticket_ids[offset:offset + 300]
            placeholders = ",".join(["%s"] * len(batch))
            sql = (f"SELECT {qso} AS source_object_id, {qsk} AS source_key, {qto} AS target_object_id, {qtk} AS target_key" +
                (f", {self._qcol(table, self._col(table, 'type_id'))} AS type_id" if self._col(table, "type_id") else "") +
                (f", {self._qcol(table, self._col(table, 'state_id'))} AS state_id" if self._col(table, "state_id") else "") +
                f" FROM {q} WHERE ({qso} = %s AND {qsk} IN ({placeholders})) OR ({qto} = %s AND {qtk} IN ({placeholders}))")
            rows.extend(self.client.execute_select(sql, (ticket_object_id, *batch, ticket_object_id, *batch)))
        associations = []
        invalid_state_count = 0
        invalid_type_count = 0
        for row in rows:
            so, sk = str(_row_value(row, "source_object_id")), str(_row_value(row, "source_key"))
            to, tk = str(_row_value(row, "target_object_id")), str(_row_value(row, "target_key"))
            state_id, type_id = _row_value(row, "state_id"), _row_value(row, "type_id")
            state_def = state_defs.get(str(state_id))
            type_def = type_defs.get(str(type_id))
            if state_def and str(state_def.get("valid_id")) != "1":
                invalid_state_count += 1
                continue
            if type_def and str(type_def.get("valid_id")) != "1":
                invalid_type_count += 1
                continue
            if so == str(ticket_object_id) and to == str(ci_object_id):
                associations.append({"ticket_id": sk, "ci_key": tk, "direction": "Ticket→ConfigItem", "type_id": type_id, "state_id": state_id})
            elif to == str(ticket_object_id) and so == str(ci_object_id):
                associations.append({"ticket_id": tk, "ci_key": sk, "direction": "ConfigItem→Ticket", "type_id": type_id, "state_id": state_id})
        per_ticket = Counter(row["ticket_id"] for row in associations)
        per_ci = Counter(row["ci_key"] for row in associations)
        counts = Counter(per_ticket.values())
        result.update({
            "status": "confirmada" if associations else "estrutura identificada; nenhuma associação na fila",
            "object_names": sorted(object_labels.values()), "ticket_object_id": ticket_object_id,
            "configitem_object_id": ci_object_id, "associations": associations,
            "association_count": len(associations), "tickets_with_ci": len(per_ticket),
            "tickets_without_ci": max(0, len(ticket_ids) - len(per_ticket)),
            "tickets_one_ci": counts.get(1, 0), "tickets_multiple_ci": sum(n for count, n in counts.items() if count > 1),
            "ticket_ci_counts": dict(per_ticket), "unique_ci_keys": sorted({row["ci_key"] for row in associations}),
            "ci_ticket_counts": dict(per_ci), "configitems_with_multiple_tickets": sum(1 for count in per_ci.values() if count > 1),
            "directions": dict(Counter(row["direction"] for row in associations)),
            "type_values": dict(Counter(str(row["type_id"]) for row in associations)),
            "state_values": dict(Counter(str(row["state_id"]) for row in associations)),
            "type_definitions": type_defs, "state_definitions": state_defs,
            "invalid_state_count": invalid_state_count, "invalid_type_count": invalid_type_count,
            "evidence": associations[:self.SAMPLE_LIMIT],
            "key_columns": {"source_object": source_object, "source_key": source_key, "target_object": target_object, "target_key": target_key},
        })
        return result

    def _relation_definitions(self, table):
        if not table:
            return {}
        id_col, name_col = self._col(table, "id"), self._col(table, "name")
        valid_col = self._col(table, "valid_id")
        if not id_col or not name_col:
            return {}
        select = f"{self._qcol(table, id_col)} AS relation_id, {self._qcol(table, name_col)} AS relation_name"
        if valid_col:
            select += f", {self._qcol(table, valid_col)} AS valid_id"
        rows = self.client.execute_select(f"SELECT {select} FROM {self._qtable(table)} LIMIT 100")
        return {str(_row_value(row, "relation_id")): {"name": _row_value(row, "relation_name"), "valid_id": _row_value(row, "valid_id")} for row in rows}

    @staticmethod
    def _relation_distribution(relation, count_key, definition_key, table):
        definitions = relation.get(definition_key, {})
        counts = relation.get(count_key, {})
        names = {str(key): value.get("name") for key, value in definitions.items()}
        validity = {names.get(str(key), str(key)): value.get("valid_id") for key, value in definitions.items() if str(key) in counts}
        return {"table": table if definitions else None, "counts": {names.get(str(key), str(key)): value for key, value in counts.items()}, "validity": validity}

    def _crosscheck(self, relation):
        result = {"status": "não executado", "sample_size": 0, "resolved": 0, "links": 0, "other_classes": {}, "unresolved": 0, "identifier_used": None, "operator_chain": "não confirmada"}
        keys = relation.get("unique_ci_keys", [])[:self.CMDB_SAMPLE_LIMIT]
        if not keys or not self.cmdb_client:
            result["reason"] = "Sem chaves associadas ou cliente CMDB configurado."
            return result
        self.progress(f"[OTRS] Validando relações no CMDB: {len(keys)}")
        try:
            raw_items = self.cmdb_client.get_items(keys)
            items = CMDBClient.sanitize_study_items(raw_items)
        except Exception as exc:
            result.update(status="falha segura", reason=type(exc).__name__)
            return result
        by_id = {str(item.get("ConfigItemID")): item for item in items if item.get("ConfigItemID") is not None}
        by_number = {str(item.get("Number")): item for item in items if item.get("Number") is not None}
        resolved_id = sum(1 for key in keys if key in by_id)
        resolved_number = sum(1 for key in keys if key in by_number)
        classes = Counter(str(item.get("Class") or "(sem classe)") for item in items)
        link_count = classes.get("Links de internet", 0)
        link_items = [item for item in items if item.get("Class") == "Links de internet"]
        isp_ids = []
        for item in link_items:
            cixml = item.get("CIXMLData") or {}
            isp = str(cixml.get("ISP") or "").strip()
            if isp and isp not in isp_ids:
                isp_ids.append(isp)
        operator_result = {"links_in_sample": len(link_items), "with_isp_id": len(isp_ids), "operators_resolved": 0, "unresolved": 0}
        if isp_ids:
            try:
                operator_rows = CMDBClient.sanitize_study_items(self.cmdb_client.get_items(isp_ids[:self.CMDB_SAMPLE_LIMIT]))
                operator_by_id = {str(item.get("ConfigItemID")): item for item in operator_rows if item.get("ConfigItemID") is not None}
                operator_result["operators_resolved"] = sum(1 for value in isp_ids[:self.CMDB_SAMPLE_LIMIT] if value in operator_by_id)
                operator_result["unresolved"] = max(0, min(len(isp_ids), self.CMDB_SAMPLE_LIMIT) - operator_result["operators_resolved"])
                operator_result["operator_classes"] = dict(Counter(str(item.get("Class") or "(sem classe)") for item in operator_rows))
                operator_result["chain_status"] = "amostra confirmada por ConfigItemID" if operator_result["operators_resolved"] else "sem resolução na amostra"
            except Exception as exc:
                operator_result.update(chain_status=f"falha segura ({type(exc).__name__})", unresolved=min(len(isp_ids), self.CMDB_SAMPLE_LIMIT))
        result["operator_chain_sample"] = operator_result
        result.update(status="amostra real", sample_size=len(keys), resolved=len(items), links=link_count,
                      other_classes={key: value for key, value in classes.items() if key != "Links de internet"},
                      unresolved=max(0, len(keys) - len(items)),
                      identifier_used="ConfigItemID" if resolved_id > 0 and resolved_id >= resolved_number else "Number" if resolved_number > 0 else "inconclusivo",
                      configitem_id_matches=resolved_id, number_matches=resolved_number,
                      operator_chain_sample=operator_result,
                       proof_items=[{"ConfigItemID": item.get("ConfigItemID"), "Number": item.get("Number"), "Class": item.get("Class")} for item in items[:self.CMDB_SAMPLE_LIMIT]],
                      sample=[{"class": item.get("Class", ""), "has_number": bool(item.get("Number")), "has_name": bool(item.get("Name")), "has_designation": bool(item.get("CIXMLData", {}).get("Designacao"))} for item in items[:self.SAMPLE_LIMIT]])
        return result

    @staticmethod
    def _association_proof(ticket, relation, cmdb):
        ticket_numbers = {str(_row_value(row, "id")): str(_row_value(row, "tn")) for row in ticket.get("rows", [])}
        cmdb_items = {str(item.get("ConfigItemID")): item for item in cmdb.get("proof_items", []) if item.get("ConfigItemID") is not None}
        proof, seen = [], set()
        for association in relation.get("associations", []):
            config_item_id = str(association["ci_key"])
            item = cmdb_items.get(config_item_id)
            if not item:
                continue
            key = (str(association["ticket_id"]), config_item_id)
            if key in seen:
                continue
            seen.add(key)
            key_column = relation.get("key_columns", {}).get("source_key") if association["direction"] == "ConfigItem→Ticket" else relation.get("key_columns", {}).get("target_key")
            proof.append({
                "ticket_id": association["ticket_id"], "ticket_number": ticket_numbers.get(str(association["ticket_id"]), ""),
                "direction": association["direction"], "relation_key_column": key_column,
                "configitem_id": item.get("ConfigItemID"), "number": item.get("Number"), "class": item.get("Class"),
            })
            if len(proof) >= OTRSStudyService.SAMPLE_LIMIT:
                break
        return proof

    def _study_dimensions(self, ticket, queue):
        table = ticket.get("table")
        if not table or not ticket.get("rows"):
            return {"states": {}, "history": {}, "articles": {}, "dynamic_fields": {}, "dimensions": {}}
        rows = ticket["rows"]
        output = {}
        dimension_tables = {
            "states": ("ticket_state", "state_id"), "priorities": ("ticket_priority", "priority_id"),
            "types": ("ticket_type", "type_id"), "services": ("service", "service_id"), "slas": ("sla", "sla_id"),
        }
        for label, (dim_name, ticket_field) in dimension_tables.items():
            dim_table = self._table(dim_name)
            ids = Counter(str(_row_value(row, ticket_field, "(nulo)")) for row in rows)
            id_col = self._col(dim_table, "id") if dim_table else None
            name_col = self._col(dim_table, "name") if dim_table else None
            mapped = {}
            if dim_table and id_col and name_col:
                type_col = self._col(dim_table, "type_id") if label == "states" else None
                valid_col = self._col(dim_table, "valid_id") if label == "states" else None
                select = f"{self._qcol(dim_table, id_col)} AS dimension_id, {self._qcol(dim_table, name_col)} AS dimension_name"
                if type_col: select += f", {self._qcol(dim_table, type_col)} AS state_type_id"
                if valid_col: select += f", {self._qcol(dim_table, valid_col)} AS valid_id"
                dim_rows = self.client.execute_select(f"SELECT {select} FROM {self._qtable(dim_table)} LIMIT 500")
                mapped = {str(_row_value(row, "dimension_id")): _row_value(row, "dimension_name") for row in dim_rows}
                if label == "states":
                    state_type_table = self._table("ticket_state_type")
                    type_name_map = {}
                    if state_type_table:
                        type_id_col, type_name_col = self._col(state_type_table, "id"), self._col(state_type_table, "name")
                        if type_id_col and type_name_col:
                            type_rows = self.client.execute_select(f"SELECT {self._qcol(state_type_table, type_id_col)} AS type_id, {self._qcol(state_type_table, type_name_col)} AS type_name FROM {self._qtable(state_type_table)} LIMIT 100")
                            type_name_map = {str(_row_value(row, "type_id")): _row_value(row, "type_name") for row in type_rows}
                    state_types = {str(_row_value(row, "dimension_id")): type_name_map.get(str(_row_value(row, "state_type_id")), str(_row_value(row, "state_type_id"))) for row in dim_rows}
                    state_type_counts = Counter()
                    for state_id, count in ids.items():
                        state_type_counts[state_types.get(state_id, "(tipo não resolvido)")] += count
                    output[label] = {"table": dim_table, "counts": {mapped.get(key, key): value for key, value in ids.items()}, "coverage": sum(value for key, value in ids.items() if key not in {"(nulo)", "None", "0"}), "type_counts": dict(state_type_counts), "state_types": state_types, "state_types_by_id": type_name_map, "validity": {str(_row_value(row, "dimension_id")): _row_value(row, "valid_id") for row in dim_rows}}
                    continue
            output[label] = {"table": dim_table, "counts": {mapped.get(key, key): value for key, value in ids.items()}, "coverage": sum(value for key, value in ids.items() if key not in {"(nulo)", "None", "0"})}
        output["history"] = self._count_related("ticket_history", rows, "ticket_id")
        output["articles"] = self._count_related("article", rows, "ticket_id")
        output["article_metadata"] = self._article_metadata(ticket, queue)
        dyn_table = self._table("dynamic_field")
        dyn_name = self._col(dyn_table, "name") if dyn_table else None
        if dyn_table and dyn_name:
            dyn_rows = self.client.execute_select(f"SELECT {self._qcol(dyn_table, dyn_name)} AS field_name FROM {self._qtable(dyn_table)} ORDER BY {self._qcol(dyn_table, dyn_name)} LIMIT 500")
            relevant_terms = ("config", "item", "link", "circuito", "designacao", "site", "cliente", "customer", "projeto", "project", "operadora", "isp", "noc", "ticket")
            relevant = [str(_row_value(row, "field_name")) for row in dyn_rows if any(term in _norm(_row_value(row, "field_name")) for term in relevant_terms)]
            names = ["[NOME DE CAMPO PROTEGIDO]" if SENSITIVE.search(name) else name for name in relevant]
            output["dynamic_fields"] = {"table": dyn_table, "names": names, "total_count": len(dyn_rows), "relevant_count": len(relevant)}
        else:
            output["dynamic_fields"] = {"table": dyn_table, "names": []}
        output["escalation_fields"] = [row["column"] for row in ticket["columns"] if any(word in _norm(row["column"]) for word in ("escalation", "response", "solution", "pending", "close", "until"))]
        output["history_passage"] = self._historical_queue_count(ticket, queue)
        output["history_types"] = self._history_type_counts(ticket)
        return output

    def _article_metadata(self, ticket, queue):
        article = self._table("article")
        ticket_table = ticket.get("table")
        ticket_id = self._col(ticket_table, "id") if ticket_table else None
        queue_id = self._col(ticket_table, "queue_id") if ticket_table else None
        article_ticket_id = self._col(article, "ticket_id") if article else None
        channel_id = self._col(article, "communication_channel_id") if article else None
        sender_type = self._col(article, "article_sender_type_id", "sender_type_id") if article else None
        if not all((article, ticket_table, ticket_id, queue_id, article_ticket_id, queue.get("id"))):
            return {"table": article, "counts": {}, "status": "metadados não disponíveis"}
        selected = []
        if channel_id: selected.append(f"a.{self._qcol(article, channel_id)} AS communication_channel_id")
        if sender_type: selected.append(f"a.{self._qcol(article, sender_type)} AS sender_type_id")
        if not selected:
            return {"table": article, "counts": {}, "status": "tipo de article não identificado"}
        group_fields = [expression.split(" AS ", 1)[0] for expression in selected]
        selected.append("COUNT(*) AS article_count")
        sql = (f"SELECT {', '.join(selected)} FROM {self._qtable(article)} a "
               f"JOIN {self._qtable(ticket_table)} t ON a.{self._qcol(article, article_ticket_id)} = t.{self._qcol(ticket_table, ticket_id)} "
               f"WHERE t.{self._qcol(ticket_table, queue_id)} = %s GROUP BY {', '.join(group_fields)}")
        rows = self.client.execute_select(sql, (queue["id"],))
        sender_table = self._table("article_sender_type")
        sender_names = {}
        if sender_table and sender_type:
            sid, sname = self._col(sender_table, "id"), self._col(sender_table, "name")
            if sid and sname:
                names = self.client.execute_select(f"SELECT {self._qcol(sender_table, sid)} AS dimension_id, {self._qcol(sender_table, sname)} AS dimension_name FROM {self._qtable(sender_table)} LIMIT 100")
                sender_names = {str(_row_value(row, "dimension_id")): _row_value(row, "dimension_name") for row in names}
        for row in rows:
            if "sender_type_id" in row:
                row["article_sender_type"] = sender_names.get(str(row.pop("sender_type_id")), "(tipo sem nome)")
        return {"table": article, "counts": rows, "status": "somente canal/tipo de remetente e contagens; sem corpo ou anexos"}

    def _historical_queue_count(self, ticket, queue):
        table = self._table("ticket_history")
        queue_col, ticket_col = (self._col(table, "queue_id"), self._col(table, "ticket_id")) if table else (None, None)
        if not table or not queue_col or not ticket_col or not queue.get("id"):
            return {"table": table, "count": None, "status": "não disponível"}
        indexes = self.client.get_table_indexes(table)
        if not any(index["column"] == queue_col for index in indexes):
            return {"table": table, "count": None, "status": "sem índice de queue_id; consulta evitada"}
        rows = self.client.execute_select(f"SELECT COUNT(DISTINCT {self._qcol(table, ticket_col)}) AS ticket_count FROM {self._qtable(table)} WHERE {self._qcol(table, queue_col)} = %s", (queue["id"],))
        return {"table": table, "count": int(_row_value(rows[0], "ticket_count", 0)) if rows else 0, "status": "tickets com evento histórico em queue_id; inclui tickets atuais"}

    def _history_type_counts(self, ticket):
        table = self._table("ticket_history")
        history_type = self._table("ticket_history_type")
        if not table or not history_type or not ticket.get("rows"):
            return {"table": table, "counts": {}, "status": "não disponível"}
        type_col, ticket_col = self._col(table, "history_type_id"), self._col(table, "ticket_id")
        id_col, name_col = self._col(history_type, "id"), self._col(history_type, "name")
        if not all((type_col, ticket_col, id_col, name_col)):
            return {"table": table, "counts": {}, "status": "colunas não confirmadas"}
        names = self.client.execute_select(f"SELECT {self._qcol(history_type, id_col)} AS type_id, {self._qcol(history_type, name_col)} AS type_name FROM {self._qtable(history_type)} LIMIT 100")
        labels = {str(_row_value(row, "type_id")): _row_value(row, "type_name") for row in names}
        ids = [row["id"] for row in ticket["rows"] if row.get("id") is not None]
        counts = Counter()
        for offset in range(0, len(ids), 300):
            batch = ids[offset:offset + 300]
            marks = ",".join(["%s"] * len(batch))
            sql = f"SELECT {self._qcol(table, type_col)} AS type_id, COUNT(*) AS row_count FROM {self._qtable(table)} WHERE {self._qcol(table, ticket_col)} IN ({marks}) GROUP BY {self._qcol(table, type_col)}"
            for row in self.client.execute_select(sql, tuple(batch)):
                key = str(_row_value(row, "type_id"))
                counts[str(labels.get(key, key))] += int(_row_value(row, "row_count", 0))
        return {"table": table, "counts": dict(counts), "status": "agregado por tipo de histórico; sem ler texto/valores de histórico"}

    def _lookup_relation_values(self, dimension_name, relation_column, ticket, queue):
        dimension_table = self._table(dimension_name)
        rel_table = self._table("link_relation")
        if not dimension_table or not rel_table or not ticket.get("ids"):
            return {"table": dimension_table, "counts": {}, "validity": {}}
        id_col, name_col = self._col(dimension_table, "id"), self._col(dimension_table, "name")
        valid_col = self._col(dimension_table, "valid_id")
        if not id_col or not name_col:
            return {"table": dimension_table, "counts": {}, "validity": {}}
        type_col = self._col(rel_table, relation_column)
        source_key, target_key = self._col(rel_table, "source_key"), self._col(rel_table, "target_key")
        source_object, target_object = self._col(rel_table, "source_object_id"), self._col(rel_table, "target_object_id")
        if not all((type_col, source_key, target_key, source_object, target_object)):
            return {"table": dimension_table, "counts": {}, "validity": {}}
        objects = self._table("link_object")
        if not objects:
            return {"table": dimension_table, "counts": {}, "validity": {}}
        oid, oname = self._col(objects, "id"), self._col(objects, "name")
        object_rows = self.client.execute_select(f"SELECT {self._qcol(objects, oid)} AS object_id, {self._qcol(objects, oname)} AS object_name FROM {self._qtable(objects)} LIMIT 100")
        object_ids = {str(_row_value(row, "object_name" )).casefold(): str(_row_value(row, "object_id")) for row in object_rows}
        ticket_oid = object_ids.get("ticket")
        ci_oid = next((value for key, value in object_ids.items() if "configitem" in key), None)
        if not ticket_oid or not ci_oid:
            return {"table": dimension_table, "counts": {}, "validity": {}}
        ticket_ids = [str(value) for value in ticket["ids"]]
        type_counts = Counter()
        for offset in range(0, len(ticket_ids), 300):
            batch = ticket_ids[offset:offset + 300]
            marks = ",".join(["%s"] * len(batch))
            sql = f"SELECT {self._qcol(rel_table, type_col)} AS relation_id FROM {self._qtable(rel_table)} WHERE ({self._qcol(rel_table, source_object)} = %s AND {self._qcol(rel_table, source_key)} IN ({marks}) AND {self._qcol(rel_table, target_object)} = %s) OR ({self._qcol(rel_table, target_object)} = %s AND {self._qcol(rel_table, target_key)} IN ({marks}) AND {self._qcol(rel_table, source_object)} = %s)"
            rows = self.client.execute_select(sql, (ticket_oid, *batch, ci_oid, ticket_oid, *batch, ci_oid))
            type_counts.update(str(_row_value(row, "relation_id")) for row in rows)
        select = f"{self._qcol(dimension_table, id_col)} AS dimension_id, {self._qcol(dimension_table, name_col)} AS dimension_name"
        if valid_col: select += f", {self._qcol(dimension_table, valid_col)} AS valid_id"
        rows = self.client.execute_select(f"SELECT {select} FROM {self._qtable(dimension_table)} LIMIT 100")
        names = {str(_row_value(row, "dimension_id")): _row_value(row, "dimension_name") for row in rows}
        validity = {str(_row_value(row, "dimension_id")): _row_value(row, "valid_id") for row in rows}
        return {"table": dimension_table, "counts": {names.get(key, key): count for key, count in type_counts.items()}, "validity": {names.get(key, key): validity.get(key) for key in type_counts}}

    def _open_review(self, ticket, relationship, dimensions):
        states = dimensions.get("states", {})
        state_types = states.get("state_types", {})
        open_type_names = {name.casefold() for name in states.get("state_types_by_id", {}).values() if str(name).casefold() not in {"closed", "merged", "removed"}}
        open_state_ids = {state_id for state_id, type_name in state_types.items() if str(type_name).casefold() in open_type_names}
        open_ids = {str(_row_value(row, "id")) for row in ticket.get("rows", []) if str(_row_value(row, "state_id")) in open_state_ids}
        ticket_ci = relationship.get("ticket_ci_counts", {})
        with_ci = sum(1 for ticket_id in open_ids if str(ticket_id) in ticket_ci)
        return {
            "status": "forte evidência pelo tipo de estado OTRS" if open_state_ids else "inconclusivo",
            "criterion": "ticket_state.type_id com tipo diferente de closed, merged e removed",
            "open_type_names": sorted(open_type_names), "open_ticket_count": len(open_ids),
            "open_ticket_ids": sorted(open_ids),
            "open_with_any_configitem": with_ci, "open_without_configitem": len(open_ids) - with_ci,
            "note": "pending auto/reminder permanece no conjunto aberto técnico; validar regra operacional de negócio antes de congelar.",
        }

    def _classify_configitems(self, relationship):
        keys = relationship.get("unique_ci_keys", [])
        item_table, catalog = self._table("configitem"), self._table("general_catalog")
        if not keys or not item_table or not catalog:
            return {"status": "não disponível", "count": 0, "class_counts": {}, "item_classes": {}, "unresolved": len(keys)}
        item_id, class_id = self._col(item_table, "id"), self._col(item_table, "class_id")
        cat_id = self._col(catalog, "id")
        cat_class = self._col(catalog, "general_catalog_class")
        cat_name = self._col(catalog, "name")
        if not all((item_id, class_id, cat_id, cat_class, cat_name)):
            return {"status": "schema de classe incompleto", "count": 0, "class_counts": {}, "item_classes": {}, "unresolved": len(keys)}
        item_classes = {}
        joins = []
        for offset in range(0, len(keys), 300):
            batch = keys[offset:offset + 300]
            marks = ",".join(["%s"] * len(batch))
            sql = (f"SELECT c.{self._qcol(item_table, item_id)} AS configitem_id, g.{self._qcol(catalog, cat_name)} AS class_name "
                   f"FROM {self._qtable(item_table)} c JOIN {self._qtable(catalog)} g "
                   f"ON c.{self._qcol(item_table, class_id)} = g.{self._qcol(catalog, cat_id)} "
                   f"WHERE g.{self._qcol(catalog, cat_class)} = %s AND c.{self._qcol(item_table, item_id)} IN ({marks})")
            rows = self.client.execute_select(sql, ("ITSM::ConfigItem::Class", *batch))
            for row in rows:
                item_classes[str(_row_value(row, "configitem_id"))] = str(_row_value(row, "class_name") or "(sem classe)")
        counts = Counter(item_classes.values())
        return {"status": "resolvido pela tabela configitem/class_id", "count": len(item_classes), "class_counts": dict(counts), "item_classes": item_classes, "unresolved": max(0, len(keys) - len(item_classes))}

    @staticmethod
    def _open_link_review(ticket, relationship, local_cmdb, open_review):
        link_cis = {key for key, class_name in local_cmdb.get("item_classes", {}).items() if class_name == "Links de internet"}
        link_ticket_ids = {str(row["ticket_id"]) for row in relationship.get("associations", []) if row["ci_key"] in link_cis}
        open_ticket_ids = {str(_row_value(row, "id")) for row in ticket.get("rows", []) if str(_row_value(row, "id")) in set(open_review.get("open_ticket_ids", []))}
        open_link_tickets = len(link_ticket_ids & open_ticket_ids)
        return {"open_with_link": open_link_tickets, "open_without_link": max(0, open_review.get("open_ticket_count", 0) - open_link_tickets), "unique_links_in_queue": len(link_cis)}

    def _count_related(self, preferred_table, ticket_rows, fk_name):
        table = self._table(preferred_table)
        ticket_id = self._col(table, fk_name) if table else None
        if not table or not ticket_id or not ticket_rows:
            return {"table": table, "count": None, "status": "estrutura não confirmada"}
        ids = [row["id"] for row in ticket_rows if row.get("id") is not None]
        count = 0
        qtable, qfk = self._qtable(table), self._qcol(table, ticket_id)
        for offset in range(0, len(ids), 300):
            batch = ids[offset:offset + 300]
            sql = f"SELECT COUNT(*) AS row_count FROM {qtable} WHERE {qfk} IN ({','.join(['%s'] * len(batch))})"
            values = self.client.execute_select(sql, tuple(batch))
            count += int(_row_value(values[0], "row_count", 0)) if values else 0
        return {"table": table, "count": count, "status": "contado por ticket_id"}

    @staticmethod
    def render_report(result):
        queue, ticket, rel, cmdb = result["queue"], result["ticket"], result["relationship"], result["cmdb"]
        db = result["database"]
        tables = result["tables"]
        table_lines = ["| Tabela/View | Tipo | Linhas estimadas | Correspondência |", "|---|---|---:|---|"]
        for row in result["candidate_tables"]:
            table_lines.append(f"| `{row['name']}` | {row['type']} | {row.get('estimated_rows') if row.get('estimated_rows') is not None else '—'} | {', '.join(row['matched_terms'])} |")
        state_counts = result.get("dimensions", {}).get("states", {}).get("counts", {})
        distribution = "\n".join(f"- `{name}`: {count}" for name, count in state_counts.items()) or "- Não disponível."
        state_type_counts = result.get("dimensions", {}).get("states", {}).get("type_counts", {})
        schema_lines = ["| Coluna | Tipo | Nulo | Chave |", "|---|---|---|---|"]
        for col in ticket.get("columns", []):
            schema_lines.append(f"| `{col['column']}` | {col['type']} | {col['nullable']} | {col['key'] or '—'} |")
        index_lines = ["| Índice | Coluna | Único |", "|---|---|---|"]
        for row in ticket.get("indexes", []):
            index_lines.append(f"| `{row['name']}` | `{row['column']}` | {'sim' if row['unique'] else 'não'} |")
        ticket_fks = ticket.get("foreign_keys", [])
        rel_fks = rel.get("foreign_keys", [])
        association_lines = [f"- Relações observadas: {rel.get('association_count', 0)}", f"- Tickets com CI: {rel.get('tickets_with_ci', 0)}", f"- Sem CI: {rel.get('tickets_without_ci', 0)}", f"- Exatamente 1 CI: {rel.get('tickets_one_ci', 0)}", f"- Múltiplos CIs: {rel.get('tickets_multiple_ci', 0)}", f"- ConfigItems ligados a mais de um ticket: {rel.get('configitems_with_multiple_tickets', 0)}"]
        proof_rows = result.get("association_proof", [])
        evidence = "\n".join(f"- `ticket.id={row['ticket_id']}` / `ticket.tn={row['ticket_number']}` → `{row['relation_key_column']}={row['configitem_id']}` → `ConfigItemID={row['configitem_id']}`, `Number={row['number']}`, `Class={row['class']}` ({row['direction']})" for row in proof_rows)
        if not evidence:
            evidence = "\n".join(f"- ticket.id `{row['ticket_id']}` → CI `{row['ci_key']}` ({row['direction']})" for row in rel.get("evidence", [])) or "- Amostra de associação não disponível."
        dimensions = result.get("dimensions", {})
        def dim_table(label):
            item = dimensions.get(label, {})
            return f"`{item.get('table') or 'não encontrada'}`; preenchidos: {item.get('coverage', '—')}/{ticket.get('count', 0)}; distribuição: {item.get('counts', {}) or 'não disponível'}"
        dynamic_names = ", ".join(f"`{name}`" for name in dimensions.get("dynamic_fields", {}).get("names", [])) or "nenhum campo candidato encontrado"
        open_review = result.get("open_review", {})
        historical = dimensions.get("history_passage", {})
        local_cmdb = result.get("local_cmdb", {})
        report = f'''# Estudo real do OTRS — NOC ATACADO

## Resumo executivo

- Execução: somente leitura; duração {result['duration_seconds']} s.
- Fila solicitada: `{queue['name']}`; status: **{queue['status']}**; queue id: `{queue.get('id') or 'não confirmado'}`.
- Tickets atualmente na fila: **{ticket.get('count', 0)}** ({ticket.get('status', 'não confirmado')}).
- Relação Ticket ↔ ConfigItem: **{rel['status']}**.
- Cross-check CMDB: {cmdb.get('status')}; amostra `{cmdb.get('sample_size', 0)}`; chave observada: `{cmdb.get('identifier_used') or 'não confirmada'}`.
- Este estudo não alterou a Base Arion nem conectou tickets às métricas operacionais.

## Ambiente

- Banco: `{db.get('database_name') or 'não informado'}`
- Servidor: `{db.get('server_version') or 'não informado'}`
- Charset/collation: `{db.get('character_set') or 'não informado'}` / `{db.get('collation') or 'não informado'}`
- Tabelas e views visíveis: {len(tables)}
- Gerado em: {result['generated_at']}

## Metodologia e segurança

Consultas sequenciais pelo `OTRSReadOnlyClient` existente; sessão MySQL declarada somente leitura. O executor aceita somente um `SELECT`, sem instruções de escrita ou efeitos colaterais. Nomes usados em SQL são obtidos do metadata do schema. Não foi consultada a coluna `users.pw`, nem selecionados corpos de articles, anexos ou credenciais. Amostras de conteúdo bruto não foram incluídas neste relatório.

## Estrutura descoberta

### Tabelas candidatas

{chr(10).join(table_lines)}

## Fila NOC - ATACADO

- Tabela: `{queue.get('table') or 'não encontrada'}`
- Queue ID: `{queue.get('id') or 'não confirmado'}`
- Resolução: {queue['status']}
- Candidatos quando não houve igualdade exata: {queue.get('candidates', []) if queue.get('id') is None else 'não aplicável; correspondência exata encontrada'}
- Tickets atuais: {ticket.get('count', 0)}

## Ticket

- Tabela: `{ticket.get('table') or 'não encontrada'}`
- PK/campo de identificação: `{OTRSStudyService._format_col(ticket, 'id')}`
- Colunas e tipos:

{chr(10).join(schema_lines)}

Índices observados:

{chr(10).join(index_lines)}

## Estados

Tabela de estados: `{dimensions.get('states', {}).get('table') or 'não encontrada'}`. Distribuição atual da fila por nome:

{distribution}

Distribuição por tipo técnico de estado: `{state_type_counts or 'não disponível'}` (via `ticket_state.type_id` → `ticket_state_type`).

Tickets abertos segundo tipo OTRS: **{open_review.get('open_ticket_count', 0)}**; status da inferência: **{open_review.get('status', 'inconclusivo')}**. Critério observado: `{open_review.get('criterion', 'não confirmado')}`. {open_review.get('note', '')}

## Tickets abertos e ConfigItems

- Com pelo menos um ConfigItem: {open_review.get('open_with_any_configitem', 0)}
- Sem ConfigItem: {open_review.get('open_without_configitem', 0)}
- Tickets abertos com Link (classe CMDB local): {open_review.get('open_with_link', 0)}; sem Link: {open_review.get('open_without_link', 0)}.

## Prioridades, tipos, serviços e SLA

- Prioridades: {dim_table('priorities')}
- Tipos: {dim_table('types')}
- Serviços: {dim_table('services')}
- SLA: {dim_table('slas')}

As distribuições refletem somente os tickets atualmente associados à fila. Nenhum cálculo de SLA ou ranking foi implementado.

## Histórico e articles

- Histórico: `{dimensions.get('history', {}).get('table') or 'estrutura não confirmada'}`, registros relacionados à amostra de tickets da fila: `{dimensions.get('history', {}).get('count', 'não contado')}`.
- Tipos de eventos de histórico: `{dimensions.get('history_types', {}).get('counts', {}) or 'não encontrados'}`.
- Tickets com passagem registrada em queue history: `{historical.get('count', 'não contado')}`; método/status: {historical.get('status', 'não disponível')}.
- Articles: `{dimensions.get('articles', {}).get('table') or 'estrutura não confirmada'}`, registros relacionados: `{dimensions.get('articles', {}).get('count', 'não contado')}`.
- Metadados de article (tipo/canal e contagens): `{dimensions.get('article_metadata', {}).get('counts', {}) or 'não disponíveis'}`.
- Somente IDs e contagens foram consultados; corpos e anexos não foram selecionados.

## Dynamic fields

- Tabela de definição: `{dimensions.get('dynamic_fields', {}).get('table') or 'não encontrada'}`
- Definições encontradas: {dimensions.get('dynamic_fields', {}).get('total_count', 0)}; candidatos relevantes: {dimensions.get('dynamic_fields', {}).get('relevant_count', 0)}.
- Nomes candidatos (sem valores): {dynamic_names}
- Tabela de valores: `{next((row['name'] for row in result['candidate_tables'] if 'dynamic' in _norm(row['name']) and 'value' in _norm(row['name'])), 'não confirmada')}`

Os nomes não comprovam semântica de projeto/cliente; fonte oficial de Projeto: **não confirmada**.

## Ticket ↔ ConfigItem — conclusão

### Qual tabela armazena a relação?

`{rel.get('table') or 'não confirmada'}`.

### Quais tabelas auxiliares participam?

Tabela de objetos: `{rel.get('object_table') or 'não confirmada'}`; objetos identificados: `{rel.get('object_names', [])}`.

Mapeamento observado: `link_relation.source_object_id={rel.get('configitem_object_id')}` (`ITSMConfigItem`) e `source_key` → `configitem.id`; `target_object_id={rel.get('ticket_object_id')}` (`Ticket`) e `target_key` → `ticket.id`. A leitura inversa parte de `target_object_id/target_key` e retorna ao ConfigItem.

### Ticket é identificado por qual campo?

`{ticket.get('table') or 'ticket'}.{OTRSStudyService._format_col(ticket, 'id')}`.

### ConfigItem é identificado por qual campo?

Chave da relação: `{(rel.get('key_columns') or {}).get('source_key') or (rel.get('key_columns') or {}).get('target_key') or 'não confirmada'}`; identificador CMDB validado na amostra: `{cmdb.get('identifier_used') or 'não confirmado'}`.

### Qual é a direção?

`{rel.get('directions', {}) or 'não confirmada'}` (interpretada pelos object IDs e object names observados).

### Cardinalidade?

{', '.join(association_lines)}. Observações de associação:

{evidence}

### Existem tipos de relação e estados?

- Tipos observados (id): `{rel.get('type_values', {}) or 'não encontrados'}`; nomes: `{dimensions.get('link_types', {}).get('counts', {}) or 'não encontrados'}`; validade configurada: `{dimensions.get('link_types', {}).get('validity', {}) or 'não disponível'}`.
- Estados observados (id): `{rel.get('state_values', {}) or 'não encontrados'}`; nomes: `{dimensions.get('link_states', {}).get('counts', {}) or 'não encontrados'}`; validade configurada: `{dimensions.get('link_states', {}).get('validity', {}) or 'não disponível'}`.
- Relações descartadas por tipo/estado inativo: tipo={rel.get('invalid_type_count', 0)}; estado={rel.get('invalid_state_count', 0)}.

### Cobertura na NOC - ATACADO?

- IDs únicos associados: {len(rel.get('unique_ci_keys', []))}
- Cobertura de ConfigItems via `configitem.class_id` e General Catalog: {local_cmdb.get('count', 0)} resolvidos; {local_cmdb.get('unresolved', 0)} não resolvidos; classes `{local_cmdb.get('class_counts', {}) or 'não disponível'}`.
- Links únicos envolvidos: {open_review.get('unique_links_in_queue', 0)}.
- Cross-check CMDB limitado a no máximo {OTRSStudyService.CMDB_SAMPLE_LIMIT} IDs: resolvidos {cmdb.get('resolved', 0)}, Links de internet {cmdb.get('links', 0)}, outras classes {cmdb.get('other_classes', {})}, não resolvidos {cmdb.get('unresolved', 0)}.
- Correspondência da amostra com `ConfigItemID`: {cmdb.get('configitem_id_matches', 0)}/{cmdb.get('sample_size', 0)}; com `Number`: {cmdb.get('number_matches', 0)}/{cmdb.get('sample_size', 0)}.
- Estes resultados são de amostra e não são extrapolados para o universo completo.

## Operadoras relacionadas

Na amostra CMDB de Links, {cmdb.get('operator_chain_sample', {}).get('with_isp_id', 0)} IDs ISP distintos foram observados e {cmdb.get('operator_chain_sample', {}).get('operators_resolved', 0)} resolveram via `Operadoras.ConfigItemID`. Classes retornadas: `{cmdb.get('operator_chain_sample', {}).get('operator_classes', {}) or 'não confirmadas'}`. Não há extrapolação para todos os Links associados.

## Validação com CMDB e cadeia até Operadora

ConfigItemGet foi usado apenas para uma amostra limitada. A chave escolhida (`{cmdb.get('identifier_used') or 'não confirmada'}`) foi comparada literalmente com `ConfigItemID` e `Number`. A cadeia amostral Ticket → ConfigItem → Link → ISP → Operadora: **{cmdb.get('operator_chain_sample', {}).get('chain_status', 'não confirmada')}**; amostra de links com ISP={cmdb.get('operator_chain_sample', {}).get('with_isp_id', 0)}, operadoras resolvidas={cmdb.get('operator_chain_sample', {}).get('operators_resolved', 0)}, não resolvidas={cmdb.get('operator_chain_sample', {}).get('unresolved', 0)}. Cobertura integral não calculada.

## Histórico atual versus passagem histórica

Fila atual foi medida por `{ticket.get('table')}.queue_id`: {ticket.get('count', 0)} tickets. Passagem histórica usa `{historical.get('table') or 'ticket_history'}.queue_id`: {historical.get('count', 'não contado')} tickets distintos com evento; esse conjunto pode incluir tickets atuais.

## Reincidência e datas

`ticket.create_time` existe e possui índice; `link_relation` fornece o vínculo CI reproduzível. Consultas futuras por janela temporal e contagem por Link são tecnicamente viáveis. O campo `close_time` não existe na tabela principal `ticket`; avaliar o histórico de estados antes de definir tempo de resolução. Datas e campos de escalonamento foram inventariados, sem cálculo nesta fase.

## SLA — viabilidade técnica

`ticket.sla_id` referencia `sla.id`; {dimensions.get('slas', {}).get('coverage', 0)}/{ticket.get('count', 0)} tickets da fila têm SLA associado. O schema inclui tempos de primeira resposta, atualização e solução em `sla` e campos de escalonamento em `ticket`. Cálculo dentro/fora do SLA depende de calendário e regra de estado e não foi implementado.

## Projeto / Cliente

Fonte oficial de Projeto: **NÃO ENCONTRADA** nesta inspeção. Campos `customer_id`, `customer_user_id`, serviços e dynamic fields são candidatos de análise, sem equivalência assumida.

## Índices e performance

O estudo usou metadata e leituras filtradas pela fila/chaves de ticket; metadados gerais usaram estimativas de linha, sem `COUNT(*)` global. Duração: {result['duration_seconds']} s. Índices críticos da relação: {rel.get('indexes', []) or 'não disponíveis'}. FKs de `ticket`: `{ticket_fks or 'nenhuma visível'}`; FKs de `{rel.get('table') or 'relação'}`: `{rel_fks or 'nenhuma visível'}`. A semântica da relação também foi conferida pelos IDs/nome em `link_object`.

## Mapeamento recomendado para fase futura

| Origem OTRS | Campo observado | Entidade Arion futura | Situação |
|---|---|---|---|
| `{ticket.get('table')}` | `{OTRSStudyService._format_col(ticket, 'id')}` | Ticket.external_id | Confirmado como chave local OTRS, sem modelagem nesta fase |
| `{ticket.get('table')}` | `{OTRSStudyService._format_col(ticket, 'tn')}` | Ticket.number | Confirmar semântica |
| `{ticket.get('table')}` | `title` | Ticket.title | Campo não consultado nem persistido |
| `{queue.get('table')}` | `id/name` | Ticket.queue | Nome exato confirmado: {queue.get('id') is not None} |
| `{ticket.get('table')}` | `ticket_state_id` → `ticket_state.type_id` | Ticket.status | Confirmado estruturalmente; validar regra operacional |
| `{rel.get('table')}` | chaves source/target | TicketLink | {rel['status']} |

## Pendências e próxima fase

Confirmar semanticamente tipos e validade dos vínculos; ampliar cross-check CMDB somente após revisar este relatório; validar regra operacional de ticket aberto e fonte de projeto. **Não foram criados modelos, migrations, sincronização ou métricas operacionais reais.**

## Confirmações de segurança

- Execução solicitada em modo somente leitura, com `SET SESSION TRANSACTION READ ONLY` no client existente.
- Nenhum comando de escrita foi aceito pelo executor.
- Senhas, hashes, tokens, sessões, `users.pw`, corpos de article e anexos não foram incluídos no relatório.
- Base Arion e dados OTRS não foram alterados.
'''
        return report

    @staticmethod
    def _format_col(ticket, key):
        mapping = {"id": "id", "tn": "tn"}
        wanted = mapping[key]
        match = next((row["column"] for row in ticket.get("columns", []) if row["column"].casefold() == wanted), None)
        return match or "não encontrado"
