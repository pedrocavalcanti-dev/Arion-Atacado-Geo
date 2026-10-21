from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .services import get_providers


@login_required
def index(request):
    providers = sorted(get_providers(), key=lambda row: row["score"], reverse=True)
    calls = sum(row["chamados"] for row in providers)
    links = sum(row["links"] for row in providers)
    weighted_sla = sum(row["dentro_sla"] for row in providers) / calls * 100 if calls else 0
    repeat_rate = sum(row["reincidencias"] for row in providers) / calls * 100 if calls else 0
    return render(request, "rankings/index.html", {
        "providers": providers,
        "total_links": links,
        "total_calls": calls,
        "average_sla": round(weighted_sla, 1),
        "average_repeat": round(repeat_rate, 1),
        "leader": providers[0],
    })
