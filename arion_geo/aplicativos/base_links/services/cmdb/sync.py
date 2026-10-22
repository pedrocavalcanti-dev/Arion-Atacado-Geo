from django.db import transaction
from django.utils import timezone
from datetime import timezone as datetime_timezone

from aplicativos.base_links.classification import _plain
from aplicativos.base_links.models import CMDBImport, CMDBLink, CMDBLinkChange, Operadora, Projeto, Provider

from .excel_provider import AUDITED_FIELDS


VALUE_FIELDS = (
    "version", "source_class", "incident_state", "deployment_state", "name", "designation_arion",
    "cnpj_arion", "address", "city", "uf", "uf_raw", "client_raw", "circuit", "isp_raw",
    "speed_raw", "range_ip", "link_type", "contract_number", "operator_designation",
    "client_identification", "business_hours", "notes", "source_created_at", "source_payload",
)


def _normalized_name(value):
    return " ".join(str(value or "").casefold().split())


def _provider(item):
    name = item.get("provider_name", "")
    if not name:
        return None
    provider, _ = Provider.objects.get_or_create(
        normalized_name=item["provider_normalized_name"],
        defaults={"name": name, "cmdb_config_item_id": item.get("provider_cmdb_config_item_id", "")},
    )
    cmdb_id = item.get("provider_cmdb_config_item_id", "")
    if cmdb_id and not provider.cmdb_config_item_id:
        provider.cmdb_config_item_id = cmdb_id
        provider.save(update_fields=("cmdb_config_item_id", "updated_at"))
    return provider


def _related(model, name):
    if not name:
        return None
    normalized = _normalized_name(name)
    obj, _ = model.objects.get_or_create(normalized_name=normalized, defaults={"name": name})
    if obj.name != name:
        obj.name = name
        obj.save(update_fields=("name", "updated_at"))
    return obj


def _relation_values(item):
    return {
        "provider": _provider(item),
        "operadora": _related(Operadora, item.get("operadora_name")),
        "projeto": _related(Projeto, item.get("projeto_name")),
    }


def _relation_display_values(item):
    return {
        "provider": item.get("provider_name", ""),
        "operadora": item.get("operadora_name", ""),
        "projeto": item.get("projeto_name", ""),
    }


def _display_value(link, field):
    value = getattr(link, field)
    if field == "provider":
        return value.name if value else ""
    if field == "operadora":
        return value.name if value else ""
    if field == "projeto":
        return value.name if value else ""
    if field == "source_created_at":
        return value.astimezone(datetime_timezone.utc).isoformat() if value else ""
    return str(value or "")


def inspect_items(items):
    existing = {row.config_item_id: row for row in CMDBLink.objects.select_related("provider", "operadora", "projeto").filter(config_item_id__in=[item["config_item_id"] for item in items])}
    result = {"new": [], "updated": [], "unchanged": [], "changes": [], "unclassified": 0}
    for item in items:
        if item["classification_status"] == "unclassified":
            result["unclassified"] += 1
        current = existing.get(item["config_item_id"])
        if current is None:
            result["new"].append({"config_item_id": item["config_item_id"], "designation": item.get("designation_arion", "")})
            continue
        pending = []
        for field in VALUE_FIELDS:
            old = _display_value(current, field)
            new = item.get(field)
            new_display = new.astimezone(datetime_timezone.utc).isoformat() if hasattr(new, "astimezone") else str(new or "")
            if old != new_display:
                pending.append({"field": field, "old": old, "new": new_display})
        relations = _relation_display_values(item)
        for field, new in relations.items():
            old = _display_value(current, field)
            new = new or ""
            if field == "provider" and current.provider and item.get("provider_normalized_name"):
                if current.provider.normalized_name == item["provider_normalized_name"]:
                    continue
            if old != new:
                pending.append({"field": field, "old": old, "new": new})
        if pending:
            result["updated"].append({"config_item_id": item["config_item_id"], "designation": item.get("designation_arion", ""), "changes": pending[:5]})
            result["changes"].extend({"config_item_id": item["config_item_id"], **change} for change in pending)
        else:
            result["unchanged"].append({"config_item_id": item["config_item_id"], "designation": item.get("designation_arion", "")})
    return result


def _status_counts(items):
    counts = {"operational": 0, "canceled": 0, "maintenance": 0, "incident": 0}
    for item in items:
        deployment = _plain(item.get("deployment_state", ""))
        incident = _plain(item.get("incident_state", ""))
        if "CANCEL" in deployment:
            counts["canceled"] += 1
        elif "MANUTEN" in deployment or "MAINTENANCE" in deployment:
            counts["maintenance"] += 1
        elif "OPERACIONAL" in deployment or "OPERATIONAL" in deployment:
            counts["operational"] += 1
        if "INCIDENT" in incident and "OPERATIONAL" not in incident:
            counts["incident"] += 1
    return counts


@transaction.atomic
def sync_items(*, items, filename, sha256, imported_by, errors=None):
    errors = errors or []
    now = timezone.now()
    status_counts = _status_counts(items)
    batch = CMDBImport.objects.create(
        filename=filename[:255], file_sha256=sha256, imported_by=imported_by,
        total_rows=len(items) + sum(error.get("row", 1) > 1 for error in errors), error_count=len(errors), unclassified_count=sum(item["classification_status"] == "unclassified" for item in items),
        operational_count=status_counts["operational"], canceled_count=status_counts["canceled"],
        maintenance_count=status_counts["maintenance"], incident_count=status_counts["incident"],
        status=CMDBImport.Status.COMPLETED_WITH_ERRORS if errors else CMDBImport.Status.COMPLETED,
    )
    CMDBLink.objects.update(is_present_in_latest_import=False)
    for item in items:
        relations = _relation_values(item)
        link = CMDBLink.objects.select_for_update().filter(config_item_id=item["config_item_id"]).first()
        if link is None:
            link = CMDBLink.objects.create(
                **{field: item.get(field) for field in VALUE_FIELDS}, **relations,
                config_item_id=item["config_item_id"], classification_status=item["classification_status"],
                synced_at=now, last_seen_import=batch, is_present_in_latest_import=True,
            )
            batch.new_count += 1
            continue

        changes = []
        is_updated = link.classification_status != item["classification_status"]
        for field in VALUE_FIELDS:
            old = _display_value(link, field)
            value = item.get(field)
            new = value.astimezone(datetime_timezone.utc).isoformat() if hasattr(value, "astimezone") else str(value or "")
            if old != new:
                is_updated = True
                setattr(link, field, value)
                if field in AUDITED_FIELDS:
                    changes.append((field, old, new))
        for field, relation in relations.items():
            old = _display_value(link, field)
            new = relation.name if relation else ""
            if old != new:
                is_updated = True
                setattr(link, field, relation)
                changes.append((field, old, new))
        link.classification_status = item["classification_status"]
        link.synced_at = now
        link.last_seen_at = now
        link.last_seen_import = batch
        link.is_present_in_latest_import = True
        link.save()
        if is_updated:
            batch.updated_count += 1
            CMDBLinkChange.objects.bulk_create([
                CMDBLinkChange(link=link, import_batch=batch, field_name=field,
                               old_value=old, new_value=new)
                for field, old, new in changes
            ])
        else:
            batch.unchanged_count += 1
    batch.save(update_fields=("new_count", "updated_count", "unchanged_count"))
    return batch
