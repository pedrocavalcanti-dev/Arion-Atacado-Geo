import csv
from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Case, CharField, Count, F, Q, When
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST
from aplicativos.configuracoes.data_scope import DataScopeService
from aplicativos.configuracoes.permissions import access_required

from aplicativos.integracoes.models import CMDBLinkMirror, CMDBOperatorMirror
from aplicativos.integracoes.services.analytics import LinkQueryService
from aplicativos.integracoes.services.semantics import LinkSemantics, UNCLASSIFIED
from .search import matching_link_queryset, normalize_search_text



@login_required
@access_required("view_base")
def index(request):
    scoped = LinkQueryService.base(request.user)
    filters = _read_filters(request)
    links = _filter_links(scoped, filters)
    sort_options = {"designation": "display_designation", "uf": "state", "provider": "operator__name", "deployment": "deployment_state"}
    sort = request.GET.get("sort", "designation")
    links = links.annotate(display_designation=Case(
        When(designation__gt="", then=F("designation")),
        When(name__gt="", then=F("name")),
        default=F("source_number"), output_field=CharField(),
    )).order_by(sort_options.get(sort, "display_designation"), "source_config_item_id")
    try:
        page_size = int(request.GET.get("page_size", "50"))
    except (TypeError, ValueError):
        page_size = 50
    if page_size not in (25, 50, 100, 200):
        page_size = 50
    page_obj = Paginator(links, page_size).get_page(request.GET.get("page"))

    kpis = scoped.aggregate(
        total=Count("pk"),
        operational=Count("pk", filter=Q(deployment_state__iexact="Operacional")),
        incidents=Count("pk", filter=Q(incident_state__iexact="Incident")),
        canceled=Count("pk", filter=Q(deployment_state__icontains="cancel")),
        providers=Count("operator_id", distinct=True),
    )
    projects = scoped.exclude(legacy_project="").values_list("legacy_project", flat=True).distinct().order_by("legacy_project")
    provider_rows = list(scoped.exclude(operator__isnull=True).values(
        "operator__source_config_item_id", "operator__name",
    ).distinct())
    provider_rows.sort(key=lambda row: (normalize_search_text(row["operator__name"]), row["operator__source_config_item_id"]))
    providers = [{"config_item_id": row["operator__source_config_item_id"], "name": row["operator__name"]} for row in provider_rows]
    if scoped.filter(operator__isnull=True).exists():
        providers.append({"name": UNCLASSIFIED})
    # Kept for downstream callers that still consume this context key; the page
    # does not present this CMDB provider catalog as contracted operators.
    operators = CMDBOperatorMirror.objects.filter(links__in=scoped).distinct().order_by("name")
    return render(request, "base_links/index.html", {
        "view": "links", "page_obj": page_obj, "links": page_obj.object_list,
        "filters": filters, "sort": sort, "page_size": page_size,
        "total_links": kpis["total"], "operational_count": kpis["operational"],
        "incident_count": kpis["incidents"], "canceled_count": kpis["canceled"],
        "provider_count": kpis["providers"], "operators": operators,
        "projects": [{"name": name} for name in projects],
        "providers": providers,
        "ufs": scoped.exclude(state="").values_list("state", flat=True).distinct().order_by("state"),
        "deployment_states": scoped.exclude(deployment_state="").values_list("deployment_state", flat=True).distinct().order_by("deployment_state"),
        "incident_states": scoped.exclude(incident_state="").values_list("incident_state", flat=True).distinct().order_by("incident_state"),
        "link_types": scoped.exclude(link_type="").values_list("link_type", flat=True).distinct().order_by("link_type"),
    })


def _read_filters(request):
    return {
        "q": request.GET.get("q", "").strip(), "projeto": request.GET.get("projeto", ""),
        "uf": request.GET.get("uf", "").strip(), "provedor": request.GET.get("provedor", "").strip(),
        "deployment_state": request.GET.get("deployment_state", ""),
        "incident_state": request.GET.get("incident_state", ""), "link_type": request.GET.get("link_type", ""),
    }


def _filter_links(queryset, filters):
    if filters["q"]:
        queryset = matching_link_queryset(queryset, filters["q"])
    for key, field in (("projeto", "legacy_project"), ("uf", "state"), ("deployment_state", "deployment_state"), ("incident_state", "incident_state"), ("link_type", "link_type")):
        if filters[key]:
            queryset = queryset.filter(**{field: filters[key]})
    if filters["provedor"]:
        from aplicativos.integracoes.services.semantics import provider_filter_queryset
        queryset = provider_filter_queryset(queryset, filters["provedor"])
    return queryset


@login_required
@access_required("view_base")
def providers(request):
    scoped = LinkQueryService.base(request.user)
    rows = CMDBOperatorMirror.objects.filter(
        is_present_in_source=True, links__in=scoped,
    ).annotate(
        link_count=Count("links", filter=Q(links__is_present_in_source=True), distinct=True),
    ).values("pk", "name", "source_config_item_id", "source_number", "link_count").distinct()
    query = request.GET.get("q", "").strip()
    if query:
        rows = rows.filter(Q(name__icontains=query) | Q(source_config_item_id__icontains=query) | Q(source_number__icontains=query))
    rows = list(rows)
    rows.sort(key=lambda row: normalize_search_text(row["name"]))
    page_obj = Paginator(rows, 100).get_page(request.GET.get("page"))
    return render(request, "base_links/providers.html", {"providers": page_obj.object_list, "page_obj": page_obj, "provider_count": len(rows), "query": query})


@login_required
@access_required("export_base")
def export_csv(request):
    queryset = _filter_links(LinkQueryService.base(request.user), _read_filters(request)).select_related("operator")
    queryset = queryset.annotate(display_designation=Case(
        When(designation__gt="", then=F("designation")),
        When(name__gt="", then=F("name")),
        default=F("source_number"), output_field=CharField(),
    )).order_by("display_designation", "source_config_item_id")
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="base-links-cmdb.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["Designação", "ConfigItem Number", "Projeto legado", "Operadora contratada", "Provedor", "Cidade", "UF", "Circuito", "Tipo", "Velocidade", "Range IP", "Implantação", "Incidente"])
    for link in queryset.iterator(chunk_size=500):
        semantics = LinkSemantics.from_link(link)
        writer.writerow([
            link.display_designation or "Não informado", link.source_number or "Não informado",
            link.legacy_project or UNCLASSIFIED, semantics.contract_operator_name or "Não classificada",
            semantics.provider_name, link.city or "Não informado", link.state or "Não informado",
            link.circuit or "Não informado", link.link_type or "Não informado", link.speed_raw or "Não informado",
            link.ip_range or "Não informado", link.deployment_state or "Não informado", link.incident_state or "Não informado",
        ])
    return response

@login_required
@access_required("view_base")
@require_GET
def provider_detail(request, pk):
    return JsonResponse({"error": "Agregacao legacy desativada; consulte os ISPs no mirror CMDB."}, status=410)


@login_required
@access_required("view_base")
@require_GET
def detail(request, pk):
    link = get_object_or_404(LinkQueryService.base(request.user).select_related("operator"), pk=pk)
    operator = link.operator
    semantics = LinkSemantics.from_link(link)
    data = {
        "id": link.pk, "config_item_id": link.source_config_item_id,
        "config_item_number": link.source_number, "version": link.version_id,
        "last_version": link.last_version_id, "definition_id": link.definition_id,
        "synced_at": link.source_synced_at.isoformat() if link.source_synced_at else None,
        "designation_arion": link.designation or link.name or link.source_number,
        "name": link.name, "operadora": semantics.contract_operator_name or "Não classificada",
        "projeto": semantics.project_name or UNCLASSIFIED,
        "project_legacy": link.legacy_project,
        "classification_status": "Não classificado", "deployment_state": link.deployment_state,
        "incident_state": link.incident_state, "provider": semantics.provider_name,
        "provider_cmdb_config_item_id": semantics.provider_config_item_id,
        "provider_cmdb_number": operator.source_number if operator else "",
        "provider_resolution_method": link.operator_resolution_method,
        "isp_raw": link.isp_raw, "speed_raw": link.speed_raw, "link_type": link.link_type,
        "range_ip": link.ip_range, "circuit": link.circuit, "equipment": link.equipment,
        "mac_address": link.mac_address, "operator_designation": link.operator_designation,
        "address": link.address, "city": link.city, "uf": link.state, "client_raw": link.customer_id,
        "contract_number": link.contract_number, "client_identification": link.identification,
        "cnpj_arion": link.cnpj, "business_hours": link.business_hours, "notes": link.isp_notes,
        "changes": [],
    }
    return JsonResponse(data)


@login_required
@access_required("view_map")
@require_GET
def map_aggregates(request):
    from django.db.models import Prefetch
    from aplicativos.integracoes.models import OTRSTicketConfigItem
    from aplicativos.integracoes.services.analytics import PeriodService, TicketQueryService
    from aplicativos.integracoes.services.semantics import LinkSemantics

    links = LinkQueryService.base(request.user)
    source_total = links.count()
    operator_id, project = request.GET.get("operator", ""), request.GET.get("project", "")
    if operator_id:
        links = links.filter(operator_id=operator_id)
    if project:
        links = links.filter(legacy_project=project)
    try:
        start, end = PeriodService.parse(request.GET)
    except ValueError:
        return JsonResponse({"error": "Intervalo de datas invalido."}, status=400)
    current_relations = OTRSTicketConfigItem.objects.filter(
        is_present_in_source=True, ticket__queue_name=TicketQueryService.QUEUE_NAME,
        ticket__is_present_in_queue=True, ticket__is_business_open=True,
    ).select_related("ticket")
    relations = OTRSTicketConfigItem.objects.filter(
        is_present_in_source=True, ticket__queue_name=TicketQueryService.QUEUE_NAME, ticket__is_present_in_queue=True,
    ).select_related("ticket")
    if start:
        relations = relations.filter(ticket__source_created_at__date__gte=start)
    if end:
        relations = relations.filter(ticket__source_created_at__date__lte=end)
    links = links.prefetch_related(
        "operator",
        Prefetch("ticket_relations", queryset=relations, to_attr="_period_ticket_relations"),
        Prefetch("ticket_relations", queryset=current_relations, to_attr="_current_open_relations"),
    )
    valid_ufs = "AC AL AP AM BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR SC SE SP TO".split()
    result = {}
    combinations = {}
    period_ticket_ids = set()
    links_with_open = set()
    state_ticket_ids = defaultdict(set)
    state_open_ticket_ids = defaultdict(set)
    state_link_ticket_counts = defaultdict(dict)
    for link in links.iterator(chunk_size=500):
        uf = (link.state or "").upper()
        if not uf:
            continue
        item = result.setdefault(uf, {"claro": 0, "vivo": 0, "algar": 0, "total_links": 0, "chamados": 0, "reincidentes": 0, "motivos": {}, "operator_counts": {}, "project_counts": {}, "open_tickets": 0, "affected_links": 0})
        item["total_links"] += 1
        if link.operator:
            name = link.operator.name
            item["operator_counts"][name] = item["operator_counts"].get(name, 0) + 1
            if name.casefold() in ("claro", "vivo", "algar"):
                item[name.casefold()] += 1
        if link.legacy_project:
            item["project_counts"][link.legacy_project] = item["project_counts"].get(link.legacy_project, 0) + 1
        scoped_relations = getattr(link, "_period_ticket_relations", [])
        ids = {relation.ticket_id for relation in scoped_relations}
        current_open_ids = {relation.ticket_id for relation in getattr(link, "_current_open_relations", [])}
        period_ticket_ids.update(ids)
        state_ticket_ids[uf].update(ids)
        state_open_ticket_ids[uf].update(current_open_ids)
        state_link_ticket_counts[uf][link.pk] = len(ids)
        if current_open_ids:
            links_with_open.add(link.pk)
            item["affected_links"] += 1
        semantics = LinkSemantics.from_link(link)
        key = (uf, link.operator_id, link.legacy_project, semantics.provider_name)
        row = combinations.setdefault(key, {"uf": uf, "provider_id": link.operator_id, "contract_operator": UNCLASSIFIED, "operator": semantics.provider_name, "project": semantics.project_name or UNCLASSIFIED, "project_legacy": link.legacy_project, "provider": semantics.provider_name, "links": 0})
        row["links"] += 1
    for uf, item in result.items():
        item["ticket_count"] = len(state_ticket_ids[uf])
        item["open_tickets"] = len(state_open_ticket_ids[uf])
        item["recurrence_links"] = sum(1 for count in state_link_ticket_counts[uf].values() if count >= 2)
    return JsonResponse({
        "mode": "cmdb", "states": result,
        "total_links": sum(item["total_links"] for item in result.values()),
        "source_total": source_total, "filtered_source_total": links.count(),
        "invalid_uf_count": links.filter(Q(state="") | ~Q(state__in=valid_ufs)).count(),
        "ticket_data_available": True, "ticket_count": len(period_ticket_ids),
        "affected_link_count": len(links_with_open),
        "operators": list(CMDBOperatorMirror.objects.filter(links__in=LinkQueryService.base(request.user)).distinct().values("id", "name")),
        "projects": list(LinkQueryService.base(request.user).exclude(legacy_project="").values_list("legacy_project", flat=True).distinct().order_by("legacy_project")),
        "combinations": list(combinations.values()),
        "period": {"date_from": start.isoformat() if start else "", "date_to": end.isoformat() if end else ""},
    })

@login_required
def import_cmdb(request):
    if not request.user.is_superuser:
        return JsonResponse({"error": "A importacao XLSX esta desativada como fonte operacional."}, status=403)
    return render(request, "base_links/import.html", {"legacy_disabled": True})


@login_required
@require_POST
def confirm_import(request):
    if not request.user.is_superuser:
        return JsonResponse({"error": "Rota XLSX LEGACY restrita ao administrador."}, status=403)
    return JsonResponse({"error": "A importacao XLSX esta desativada como fonte operacional."}, status=410)
