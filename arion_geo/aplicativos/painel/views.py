from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.conf import settings
from pathlib import Path
import json


STATE_NAMES = {
    "AC": "Acre", "AL": "Alagoas", "AM": "Amazonas", "AP": "Amapá", "BA": "Bahia",
    "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás",
    "MA": "Maranhão", "MG": "Minas Gerais", "MS": "Mato Grosso do Sul", "MT": "Mato Grosso",
    "PA": "Pará", "PB": "Paraíba", "PE": "Pernambuco", "PI": "Piauí", "PR": "Paraná",
    "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RO": "Rondônia", "RR": "Roraima",
    "RS": "Rio Grande do Sul", "SC": "Santa Catarina", "SE": "Sergipe", "SP": "São Paulo", "TO": "Tocantins",
}
REGIONS = {
    "Norte": ("AC", "AP", "AM", "PA", "RO", "RR", "TO"),
    "Nordeste": ("AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"),
    "Centro-Oeste": ("DF", "GO", "MS", "MT"),
    "Sudeste": ("ES", "MG", "RJ", "SP"),
    "Sul": ("PR", "RS", "SC"),
}
MONTHS = (("Mai", "Maio"), ("Jun", "Junho"), ("Jul", "Julho"), ("Ago", "Agosto"), ("Set", "Setembro"), ("Out", "Outubro"))


def share(value, whole):
    return round(value / whole * 100, 1) if whole else 0


@login_required
def index(request):
    return render(request, "painel/index.html", {"state_count": len(STATE_NAMES)})


@login_required
def dashboard(request):
    data_path = Path(settings.BASE_DIR) / "static" / "data" / "mapa-demo.json"
    states = json.loads(data_path.read_text(encoding="utf-8"))
    total = lambda field: sum(row[field] for row in states.values())
    links, calls, repeat = total("total_links"), total("chamados"), total("reincidentes")
    operators = [{"name": name, "value": total(key), "key": key, "share": share(total(key), links)}
                 for name, key in (("Claro", "claro"), ("Vivo", "vivo"), ("Algar", "algar"))]
    regions = [{"name": name, "value": value, "share": share(value, calls)}
               for name, value in ((name, sum(states[code]["chamados"] for code in codes))
                                   for name, codes in REGIONS.items())]
    top_states = sorted(({"code": code, "name": STATE_NAMES[code], "value": row["total_links"],
                          "flag": f"imagens/bandeiras/estados/{code.lower()}.svg"}
                         for code, row in states.items()), key=lambda item: item["value"], reverse=True)[:5]
    reasons = [("Falha massiva", 21), ("Rompimento de fibra", 18), ("Troca de drop", 15),
               ("Equipamento", 13), ("Cabo desconectado", 11), ("Falha elétrica", 9), ("Outros", 13)]
    monthly = [{"month": month, "label": label, "calls": round(calls * factor), "repeat": round(repeat * factor)}
               for (month, label), factor in zip(MONTHS, (0.68, 0.76, 0.82, 0.91, 0.87, 1))]
    context = {
        "total_links": links, "state_count": len(states), "calls": calls,
        "repeat": repeat, "repeat_share": share(repeat, calls), "first_calls": calls - repeat,
        "operator_count": len(operators),
        "operators": operators, "regions": regions, "top_states": top_states,
        "reasons": [{"name": name, "value": value} for name, value in reasons], "monthly": monthly,
    }
    return render(request, "painel/dashboard.html", context)
