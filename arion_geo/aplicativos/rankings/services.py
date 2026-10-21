import json
from pathlib import Path

from django.conf import settings


def get_providers():
    """Load the demo source and derive a reproducible 0-100 operational score."""
    path = Path(settings.BASE_DIR) / "static" / "data" / "rankings-demo.json"
    providers = json.loads(path.read_text(encoding="utf-8"))
    total_links = sum(row.get("links", 0) for row in providers) or 1
    states = ["SP", "RJ", "MG", "PR", "DF"]
    reasons = ["Falha de fibra", "Instabilidade", "Equipamento", "Energia", "Outros"]
    for index, provider in enumerate(providers):
        total = provider["chamados"]
        links = provider.get("links", 0)
        sla = provider["dentro_sla"] / total * 100 if total else 0
        outside = provider["fora_sla"] / total * 100 if total else 0
        repeat = provider["reincidencias"] / total * 100 if total else 0
        score = (sla * .45 + provider["avaliacao"] / 5 * 100 * .25
                 + provider["uptime"] * .20 + (100 - repeat * 2) * .06
                 + (100 - outside) * .04)
        provider["score"] = round(max(0, min(100, score)), 1)
        provider["logo"] = "".join(part[0] for part in provider["nome"].split()[:2]).upper()
        provider["dentro_pct"] = round(sla, 1)
        provider["repeat_pct"] = round(repeat, 1)
        provider["links"] = links
        provider["links_share"] = round(links / total_links * 100, 1)
        # Detalhamento sintético e estável para a demonstração do drawer.
        provider["operators"] = [provider["operadora"]]
        provider["projects"] = [{"name": provider["projeto"], "links": links}]
        shares = [48, 22, 14, 10, 6]
        shares = shares[index % 5:] + shares[:index % 5]
        allocations = [links * share // 100 for share in shares]
        allocations[0] += links - sum(allocations)
        provider["states"] = [{"uf": uf, "links": count} for uf, count in zip([provider["uf"], *[s for s in states if s != provider["uf"]][:4]], allocations)]
        weights = [36 + index % 7, 25, 18, 12, 9]
        reason_counts = [total * weight // sum(weights) for weight in weights]
        reason_counts[0] += total - sum(reason_counts)
        provider["reasons"] = [{"name": name, "count": count} for name, count in zip(reasons, reason_counts)]
        # Série histórica mensal derivada da base atual, sem aleatoriedade.
        factors = [0.82, 0.89, 0.94, 1.04, 1.05, 1.0]
        provider["history"] = [round(total * factor) for factor in factors]
        provider["score_parts"] = {
            "SLA": round(sla * .45, 1),
            "Avaliação": round(provider["avaliacao"] / 5 * 100 * .25, 1),
            "Disponibilidade": round(provider["uptime"] * .20, 1),
            "Reincidência": round((100 - repeat * 2) * .06, 1),
            "Fora do SLA": round((100 - outside) * .04, 1),
        }
        provider["alerts"] = [label for condition, label in (
            (outside >= 8, "SLA abaixo da meta global"),
            (repeat >= 12, "Reincidência acima da faixa esperada"),
            (provider["estourados"] >= 4, "Chamados críticos estourados"),
        ) if condition]
    return providers
