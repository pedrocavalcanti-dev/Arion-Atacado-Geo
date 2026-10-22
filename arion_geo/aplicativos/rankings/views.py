from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from aplicativos.base_links.data_source import get_data_source_mode
from aplicativos.base_links.models import CMDBImport, CMDBLink, Operadora, Projeto
from aplicativos.base_links.services.provider_aggregation import get_provider_aggregates
from aplicativos.base_links.models import CMDBLink
from aplicativos.configuracoes.data_scope import DataScopeService
from aplicativos.configuracoes.permissions import access_required
from .performance import DemoProviderPerformanceSource


@login_required
@access_required("view_rankings")
def index(request):
    period = request.GET.get("period", "2026-10")
    source = DemoProviderPerformanceSource()
    scoped_links = DataScopeService.filter_queryset(request.user, CMDBLink.objects.all())
    providers, total_links = get_provider_aggregates(base_queryset=scoped_links)
    for provider in providers:
        performance = source.get(provider["id"], provider["links"], period)
        provider.update(performance)
        provider["nome"] = provider["name"]
        provider["logo"] = "".join(part[0] for part in provider["name"].split()[:2]).upper()
        provider["links_share"] = provider["share"]
        provider["operadoras"] = [row["name"] for row in provider["operators"]]
        provider["projetos_nomes"] = [row["name"] for row in provider["projects"]]
        provider["operadora"] = ", ".join(provider["operadoras"]) or "Não classificada"
        provider["projeto"] = ", ".join(provider["projetos_nomes"][:2]) or "Não classificado"
        provider["uf"] = provider["states"][0]["uf"] if provider["states"] else "—"
        provider["repeat_pct"] = performance["repeat_pct"]
        provider["alerts"] = []
        provider["score_parts"] = {}
        provider["reasons"] = []
        provider["fora_sla"] = performance["fora_sla"]
        provider["dentro_pct"] = performance["dentro_pct"]
        provider["cmdb_config_item_id"] = provider["cmdb_config_item_id"] or ""

    sort_key = request.GET.get("sort", "score")
    sorters = {
        "links": lambda item: (-item["links"], item["name"].casefold()),
        "score": lambda item: (-item["score"], item["name"].casefold()),
    }
    providers.sort(key=sorters.get(sort_key, sorters["score"]))
    largest_provider = max(providers, key=lambda item: item["links"], default={})
    calls = sum(item["chamados"] for item in providers)
    average_sla = sum(item["dentro_sla"] for item in providers) / calls * 100 if calls else 0
    average_repeat = sum(item["reincidencias"] for item in providers) / calls * 100 if calls else 0
    return render(request, "rankings/index.html", {
        "providers": providers, "total_links": total_links, "total_calls": calls,
        "average_sla": round(average_sla, 1), "average_repeat": round(average_repeat, 1),
        "leader": providers[0] if providers else {}, "data_source_mode": "cmdb",
        "largest_provider": largest_provider,
        "provider_count": len(providers), "latest_import": CMDBImport.objects.first(),
        "operators": Operadora.objects.filter(links__in=scoped_links, links__is_present_in_latest_import=True).distinct(),
        "projects": Projeto.objects.filter(links__in=scoped_links, links__is_present_in_latest_import=True).distinct(),
        "period": period,
    })
