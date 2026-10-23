"""Deprecated XLSX provider aggregation retained for rollback only.

Operational routes do not import this module.
"""
"""Shared CMDB-only provider aggregates used by Base and Rankings."""
from django.db.models import Count, Q

from aplicativos.base_links.models import CMDBLink


INVALID_PROVIDER_NAMES = {
    "", "-", "--", "n/a", "na", "n.a.", "n.d.", "nao informado", "n\u00e3o informado",
    "nao disponivel", "n\u00e3o dispon\u00edvel", "sem informacao", "sem informa\u00e7\u00e3o",
    "unknown", "desconhecido", "null", "none", "undefined", "placeholder",
}


def provider_link_queryset(*, operator_id="", project_id="", uf="", provider_id="", query="", latest=True, base_queryset=None):
    links = (base_queryset if base_queryset is not None else CMDBLink.objects.all()).filter(provider__isnull=False)
    if latest:
        links = links.filter(is_present_in_latest_import=True)
    links = links.exclude(provider__normalized_name__in=INVALID_PROVIDER_NAMES)
    if operator_id:
        links = links.filter(operadora_id=operator_id)
    if project_id:
        links = links.filter(projeto_id=project_id)
    if uf:
        links = links.filter(uf=uf.upper())
    if provider_id:
        links = links.filter(provider_id=provider_id)
    if query:
        links = links.filter(Q(provider__name__icontains=query) | Q(provider__cmdb_config_item_id__icontains=query))
    return links


def get_provider_aggregates(*, operator_id="", project_id="", uf="", provider_id="", query="", latest=True, base_queryset=None):
    """Return real link counts and grouped coverage without per-provider queries."""
    links = provider_link_queryset(operator_id=operator_id, project_id=project_id, uf=uf, provider_id=provider_id, query=query, latest=latest, base_queryset=base_queryset)
    scoped_base = base_queryset if base_queryset is not None else CMDBLink.objects.all()
    total_links = scoped_base.filter(is_present_in_latest_import=True).count() if latest else scoped_base.count()
    rows = list(links.values("provider_id", "provider__name", "provider__cmdb_config_item_id").annotate(
        link_count=Count("id"), classified_links=Count("id", filter=Q(operadora__isnull=False, projeto__isnull=False)),
    ).order_by("provider__name"))
    # Grouped lookups keep the detail view bounded to a few queries, regardless of provider count.
    result = {row["provider_id"]: {
        "id": row["provider_id"], "name": row["provider__name"], "cmdb_config_item_id": row["provider__cmdb_config_item_id"],
        "links": row["link_count"], "share": round(row["link_count"] / total_links * 100, 1) if total_links else 0,
        "classified_links": row["classified_links"], "unclassified_links": row["link_count"] - row["classified_links"],
        "projects": [], "operators": [], "states": [], "cities": [],
    } for row in rows if row["link_count"] > 0}
    if not result:
        return [], total_links
    for row in links.filter(provider_id__in=result, projeto__isnull=False).values("provider_id", "projeto__name").annotate(count=Count("id")).order_by("provider_id", "-count"):
        result[row["provider_id"]]["projects"].append({"name": row["projeto__name"], "links": row["count"]})
    for row in links.filter(provider_id__in=result, operadora__isnull=False).values("provider_id", "operadora__name").annotate(count=Count("id")).order_by("provider_id", "operadora__name"):
        result[row["provider_id"]]["operators"].append({"name": row["operadora__name"], "links": row["count"]})
    for row in links.filter(provider_id__in=result).exclude(uf="").values("provider_id", "uf").annotate(count=Count("id")).order_by("provider_id", "-count"):
        result[row["provider_id"]]["states"].append({"uf": row["uf"], "links": row["count"]})
    for row in links.filter(provider_id__in=result).exclude(city="").values("provider_id", "city").annotate(count=Count("id")).order_by("provider_id", "-count"):
        result[row["provider_id"]]["cities"].append({"name": row["city"], "links": row["count"]})
    return sorted(result.values(), key=lambda item: (-item["links"], item["name"].casefold())), total_links

