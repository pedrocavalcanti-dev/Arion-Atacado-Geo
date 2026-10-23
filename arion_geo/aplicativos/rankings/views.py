from datetime import date
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET

from aplicativos.configuracoes.permissions import access_required
from aplicativos.integracoes.models import CMDBOperatorMirror
from aplicativos.integracoes.services.analytics import LinkQueryService, PeriodService
from .services import RankingService

SORT_OPTIONS = (("tickets", "Mais tickets"), ("open_tickets", "Mais abertos"), ("affected_links", "Mais links afetados"), ("recurrence_links", "Mais reincidentes"), ("tickets_per_link", "Tickets por link"), ("links", "Mais links CMDB"))
SORT_KEYS = {key for key, _ in SORT_OPTIONS}
PAGE_SIZES = (25, 50, 100)


def _read_filters(request):
    today = date.today()
    try:
        start, end = PeriodService.parse(request.GET)
    except ValueError:
        start, end = None, None
    start = start or today.replace(day=1)
    end = end or today
    sort = request.GET.get("sort", "tickets")
    if sort not in SORT_KEYS:
        sort = "tickets"
    try:
        page_size = int(request.GET.get("page_size", 25))
    except (TypeError, ValueError):
        page_size = 25
    if page_size not in PAGE_SIZES:
        page_size = 25
    return {"date_from": start.isoformat(), "date_to": end.isoformat(),
            "operator": request.GET.get("operator", "").strip(),
            "project": request.GET.get("project", "").strip(),
            "q": request.GET.get("q", "").strip()[:100], "sort": sort, "page_size": page_size}


def _url(filters, **updates):
    values = {key: value for key, value in filters.items() if value not in ("", None)}
    values.update(updates)
    return "?" + urlencode(values)


def _build(request, filters):
    start, end = PeriodService.parse(filters)
    return RankingService.build(request.user, date_from=start, date_to=end,
        operator_id=filters["operator"], project=filters["project"], query=filters["q"])


@login_required
@access_required("view_rankings")
def index(request):
    filters = _read_filters(request)
    operators, links, total_links, summary = _build(request, filters)
    operators.sort(key=lambda row: (-row.get(filters["sort"], 0), row["name"].casefold()))
    for index, item in enumerate(operators, 1):
        item["ranking_position"] = index
    page_obj = Paginator(operators, filters["page_size"]).get_page(request.GET.get("page"))
    scope_links = LinkQueryService.base(request.user)
    return render(request, "rankings/index.html", {
        "operators": operators, "page_obj": page_obj, "ranked_links": links[:100],
        "top_operators": operators[:3], "leader": operators[0] if operators else None,
        "total_links": total_links, "total_tickets": summary["tickets"], "open_tickets": summary["open_tickets"],
        "operator_count": len(operators), "affected_links": sum(item["affected_links"] for item in operators),
        "filters": filters,
        "sort_options": [{"value": key, "label": label, "url": _url(filters, sort=key), "active": key == filters["sort"]} for key, label in SORT_OPTIONS],
        "operators_filter": CMDBOperatorMirror.objects.filter(links__in=scope_links).distinct().order_by("name"),
        "projects": scope_links.exclude(legacy_project="").values_list("legacy_project", flat=True).distinct().order_by("legacy_project"),
        "page_sizes": PAGE_SIZES,
        "provider_detail_url_template": reverse("rankings:provider-detail", args=[0]),
        "base_url": reverse("base_links:index"),
    })


@login_required
@access_required("view_rankings")
@require_GET
def provider_detail(request, provider_id):
    filters = _read_filters(request)
    operators, _links, _total, _summary = _build(request, filters)
    item = next((row for row in operators if str(row["id"]) == str(provider_id)), None)
    if item is None:
        return JsonResponse({"error": "Operadora nao encontrada no escopo atual."}, status=404)
    return JsonResponse(item)
