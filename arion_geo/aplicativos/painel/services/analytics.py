import hashlib
from collections import defaultdict

from django.db.models import Count

from aplicativos.base_links.models import CMDBLink
from aplicativos.configuracoes.data_scope import DataScopeService


METRICS = {
    "links": ("Links", "real", "neutral"), "tickets": ("Chamados", "demo", "negative"),
    "open_tickets": ("Abertos", "demo", "negative"), "closed_tickets": ("Fechados", "demo", "neutral"),
    "recurrences": ("Reincidências", "demo", "negative"), "sla_met": ("SLA cumprido", "demo", "positive"),
    "sla_missed": ("SLA perdido", "demo", "negative"), "avg_resolution_time": ("Tempo médio", "demo", "negative"),
    "backlog": ("Backlog", "demo", "negative"),
}
DIMENSIONS = {"month": "Mês", "operator": "Operadora", "project": "Projeto", "provider": "ISP", "uf": "UF", "reason": "Motivo", "status": "Status", "sla_status": "SLA"}
LINK_DIMENSIONS = {"month", "operator", "project", "provider", "uf"}
FILTERS = {"operator", "project", "provider", "uf", "reason", "status", "sla_status"}
REASONS = ("Pendência Financeira", "Falha Massiva", "Rompimento de Fibra", "Troca de Drop", "Equipamento", "Falha Elétrica", "Sem Intervenção", "Indisponibilidade", "Configuração", "Outros")
STATUSES = ("Aberto", "Em atendimento", "Pendente", "Resolvido", "Fechado")
MONTHS = tuple(f"2026-{month:02d}" for month in range(1, 11))
MONTH_SHORT = ("Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out")


def stable_int(seed, modulo):
    return int.from_bytes(hashlib.sha256(seed.encode("utf-8")).digest()[:8], "big") % modulo


class CMDBAnalyticsSource:
    """Real CMDB facets queried with database-side grouping."""
    def rows(self, user=None):
        queryset = CMDBLink.objects.filter(is_present_in_latest_import=True)
        if user is not None:
            queryset = DataScopeService.filter_queryset(user, queryset)
        return list(queryset.values(
            "uf", "operadora__name", "projeto__name", "provider__name",
        ).annotate(links=Count("id")))


class DemoOperationalAnalyticsSource:
    """Stable operational estimates derived from current CMDB combinations."""
    def expand(self, rows):
        result = []
        for row in rows:
            base = f"{row['uf']}|{row['operadora__name']}|{row['projeto__name']}|{row['provider__name']}"
            for month in MONTHS:
                tickets = round(row["links"] * (0.035 + stable_int(base + month, 75) / 1000))
                recurrences = min(tickets, round(tickets * (0.08 + stable_int(base + month + 'r', 21) / 100)))
                result.append({**row, "month": month, "tickets": tickets, "recurrences": recurrences,
                               "reason": REASONS[stable_int(base + month + 'reason', len(REASONS))],
                               "status": STATUSES[stable_int(base + month + 'status', len(STATUSES))],
                               "sla_status": "Cumprido" if stable_int(base + month + 'sla', 100) < 84 else "Perdido"})
        return result


class OTRSOperationalAnalyticsSource:
    """Future source contract; ticket schema is intentionally not assumed yet."""
    def expand(self, rows):
        raise NotImplementedError("A integração OTRS será implementada quando o schema estiver disponível.")


class AnalyticsQueryService:
    def __init__(self, cmdb=None, demo=None):
        self.cmdb = cmdb or CMDBAnalyticsSource()
        self.demo = demo or DemoOperationalAnalyticsSource()

    def query(self, payload, user=None):
        metric, group = payload.get("metric", "tickets"), payload.get("group_by", "month")
        if metric not in METRICS: raise ValueError("Métrica não autorizada.")
        if group not in DIMENSIONS or (metric == "links" and group not in LINK_DIMENSIONS): raise ValueError("Dimensão não autorizada para esta métrica.")
        period, compare = payload.get("period", "2026-10"), payload.get("compare_to")
        period_from, period_to = payload.get("period_from", MONTHS[0]), payload.get("period_to", MONTHS[-1])
        if period not in MONTHS or period_from not in MONTHS or period_to not in MONTHS or MONTHS.index(period_from) > MONTHS.index(period_to) or not MONTHS.index(period_from) <= MONTHS.index(period) <= MONTHS.index(period_to) or (compare is not None and compare not in MONTHS): raise ValueError("Período inválido.")
        filters = payload.get("filters", {})
        if not isinstance(filters, dict) or set(filters) - FILTERS: raise ValueError("Filtro não autorizado.")
        rows = self.cmdb.rows(user=user)
        filtered = [r for r in rows if self._matches(r, filters)]
        operational = self.demo.expand(filtered)
        series = []
        for month in MONTHS[MONTHS.index(period_from):MONTHS.index(period_to) + 1]:
            month_index = int(month[-2:]) - 1
            series.append({"key": month, "label": f"{MONTH_SHORT[month_index]}/26", "long_label": f"{MONTH_SHORT[month_index]} de 2026", "value": self._sum(filtered, operational, metric, month, filters)})
        current = next(x["value"] for x in series if x["key"] == period)
        previous = self._sum(filtered, operational, metric, compare, filters) if compare is not None else None
        comparison = None if compare is None else {"value": previous, "difference": current - previous,
            "percent": round((current - previous) / previous * 100, 1) if previous else (0 if current == 0 else None),
            "direction": METRICS[metric][2]}
        breakdown = defaultdict(float)
        group_counts = defaultdict(float)
        if group == "month":
            for item in series:
                breakdown[item["key"]] = item["value"]
                group_counts[item["key"]] = item["value"]
        elif metric == "links":
            for row in filtered:
                key = self._dimension_value(row, group, period)
                if key is not None:
                    breakdown[key] += row["links"]
        else:
            for row in operational:
                if row["month"] != period or not self._operational_matches(row, filters):
                    continue
                key = self._dimension_value(row, group, period)
                if key is not None:
                    amount = self._operational_value(row, metric)
                    if metric == "avg_resolution_time":
                        group_counts[key] += row["tickets"]
                    breakdown[key] += amount
        all_breakdown = sorted(breakdown.items(), key=lambda item: (-item[1], str(item[0]).casefold()))
        ordered_breakdown = all_breakdown[:20]
        if metric == "avg_resolution_time" and group != "month":
            all_breakdown = [(key, value / group_counts[key] if group_counts[key] else 0) for key, value in all_breakdown]
            ordered_breakdown = all_breakdown[:20]
        detail_total = sum(group_counts.values()) if metric == "avg_resolution_time" and group != "month" else (sum(value for _, value in all_breakdown) if group == "month" else current)
        detail = [{"dimension": str(key), "value": round(value, 2),
                   "share": round((group_counts[key] if metric == "avg_resolution_time" and group != "month" else value) / detail_total * 100, 1) if detail_total else 0}
                  for key, value in all_breakdown]
        kpis = self._contextual_kpis(metric, filtered, operational, period, filters)
        return {"metric": metric, "metric_label": METRICS[metric][0], "group_by": group,
                "group_by_label": DIMENSIONS[group], "source": METRICS[metric][1],
                "period": period, "period_from": period_from, "period_to": period_to, "compare_to": compare,
                "value": current, "comparison": comparison, "series": series,
                "breakdown": [{"key": key, "value": round(value, 2)} for key, value in ordered_breakdown],
                "detail": detail, "kpis": kpis,
                "provider_count": len({r["provider__name"] for r in filtered if r["provider__name"]}),
                "options": self.options(rows), "meta": {"demo": METRICS[metric][1] == "demo"}}

    @staticmethod
    def _dimension_value(row, group, period):
        if group == "month":
            return period
        fields = {"operator": "operadora__name", "project": "projeto__name", "provider": "provider__name", "uf": "uf"}
        if group in fields:
            return row.get(fields[group]) or "Não classificado"
        if group in ("reason", "status", "sla_status"):
            return row.get(group)
        return None

    @staticmethod
    def _operational_matches(row, filters):
        return all(key not in ("reason", "status", "sla_status") or value in (None, "", "all") or row[key] == value
                   for key, value in filters.items())

    @staticmethod
    def _operational_value(row, metric):
        tickets = row["tickets"]
        return {
            "tickets": tickets,
            "open_tickets": tickets if row["status"] in STATUSES[:3] else 0,
            "closed_tickets": tickets if row["status"] in STATUSES[3:] else 0,
            "recurrences": row["recurrences"],
            "sla_met": tickets if row["sla_status"] == "Cumprido" else 0,
            "sla_missed": tickets if row["sla_status"] == "Perdido" else 0,
            "avg_resolution_time": tickets * (2 + stable_int(str(row), 48) / 10),
            "backlog": tickets if row["status"] in STATUSES[:3] else 0,
        }[metric]

    def _contextual_kpis(self, metric, base, operational, period, filters):
        period_rows = [row for row in operational if row["month"] == period and self._operational_matches(row, filters)]
        tickets = sum(row["tickets"] for row in period_rows)
        recurring = sum(row["recurrences"] for row in period_rows)
        within_sla = sum(row["tickets"] for row in period_rows if row["sla_status"] == "Cumprido")
        outside_sla = sum(row["tickets"] for row in period_rows if row["sla_status"] == "Perdido")
        if metric == "links":
            values = [("Links", sum(row["links"] for row in base), "real"),
                      ("Provedores", len({row["provider__name"] for row in base if row["provider__name"]}), "real"),
                      ("UFs", len({row["uf"] for row in base if row["uf"]}), "real"),
                      ("Operadoras", len({row["operadora__name"] for row in base if row["operadora__name"]}), "real")]
        elif metric in ("recurrences",):
            affected = sum(1 for row in period_rows if row["recurrences"])
            values = [("Chamados", tickets, "demo"), ("Reincidentes", recurring, "demo"),
                      ("Taxa de reincidência", round(recurring / tickets * 100, 1) if tickets else 0, "demo", "%"),
                      ("Links afetados", affected, "demo")]
        elif metric in ("sla_met", "sla_missed"):
            values = [("Chamados", tickets, "demo"), ("Dentro do SLA", within_sla, "demo"),
                      ("Fora do SLA", outside_sla, "demo"),
                      ("Cumprimento", round(within_sla / (within_sla + outside_sla) * 100, 1) if within_sla + outside_sla else 0, "demo", "%")]
        else:
            current = self._sum(base, period_rows, metric, period, filters)
            open_count = sum(row["tickets"] for row in period_rows if row["status"] in STATUSES[:3])
            if metric == "tickets":
                extras = [("Abertos", open_count, "demo"), ("Reincidentes", recurring, "demo"),
                          ("Provedores", len({row["provider__name"] for row in base if row["provider__name"]}), "real")]
            elif metric == "closed_tickets":
                extras = [("Chamados", tickets, "demo"), ("Dentro do SLA", within_sla, "demo"), ("Reincidentes", recurring, "demo")]
            elif metric == "avg_resolution_time":
                extras = [("Chamados", tickets, "demo"), ("Abertos", open_count, "demo"), ("Dentro do SLA", within_sla, "demo")]
            else:
                extras = [("Chamados", tickets, "demo"), ("Reincidentes", recurring, "demo"),
                          ("Links com chamados", sum(1 for row in period_rows if row["tickets"]), "demo")]
            values = [(METRICS[metric][0], round(current, 1), "demo"), *extras]
        result = []
        for item in values:
            label, value, source, *unit = item
            result.append({"label": label, "value": value, "source": source, "unit": unit[0] if unit else ""})
        return result

    def dashboard_snapshot(self, user=None):
        """National Demo series used by the executive dashboard and this query service."""
        rows = self.cmdb.rows(user=user)
        operational = self.demo.expand(rows)
        monthly = []
        for index, month in enumerate(MONTHS):
            monthly.append({
                "month": MONTH_SHORT[index], "label": f"{MONTH_SHORT[index]}/26",
                "calls": self._sum(rows, operational, "tickets", month, {}),
                "repeat": self._sum(rows, operational, "recurrences", month, {}),
            })
        return {"monthly": monthly, "calls": monthly[-1]["calls"], "repeat": monthly[-1]["repeat"]}

    @staticmethod
    def _matches(row, filters):
        fields = {"operator": "operadora__name", "project": "projeto__name", "provider": "provider__name", "uf": "uf"}
        for key, value in filters.items():
            if value in (None, "", "all"): continue
            if key == "operator" and value == "Não classificado":
                if row.get("operadora__name"): return False
                continue
            if key in fields and str(row.get(fields[key]) or "").casefold() != str(value).casefold(): return False
        return True

    @staticmethod
    def _sum(base, operational, metric, month, filters):
        if metric == "links": return sum(r["links"] for r in base)
        rows = [r for r in operational if r["month"] == month]
        rows = [r for r in rows if all(k not in ("reason", "status", "sla_status") or v in (None, "", "all") or r[k] == v for k, v in filters.items())]
        funcs = {"tickets": lambda r: r["tickets"], "open_tickets": lambda r: r["tickets"] if r["status"] in STATUSES[:3] else 0,
                 "closed_tickets": lambda r: r["tickets"] if r["status"] in STATUSES[3:] else 0,
                 "recurrences": lambda r: r["recurrences"], "sla_met": lambda r: r["tickets"] if r["sla_status"] == "Cumprido" else 0,
                 "sla_missed": lambda r: r["tickets"] if r["sla_status"] == "Perdido" else 0,
                 "avg_resolution_time": lambda r: r["tickets"] * (2 + stable_int(str(r), 48) / 10),
                 "backlog": lambda r: r["tickets"] if r["status"] in STATUSES[:3] else 0}
        total = sum(funcs[metric](r) for r in rows)
        if metric == "avg_resolution_time": return round(total / max(1, sum(r["tickets"] for r in rows)), 1)
        return total

    def _group_values(self, row, operational, metric, group, month, filters):
        names = {"operator": row["operadora__name"], "project": row["projeto__name"], "provider": row["provider__name"], "uf": row["uf"]}
        if group == "month": return [(r["month"], self._sum([row], [r], metric, r["month"], filters)) for r in operational if r["month"] == month] if metric != "links" else [(month, row["links"])]
        if group in names: return [(names[group] or "Não classificado", self._sum([row], [r for r in operational if r["month"] == month], metric, month, filters))]
        return []

    @staticmethod
    def options(rows):
        return {key: sorted({str(r[field]) for r in rows if r[field]}) for key, field in (("operator", "operadora__name"), ("project", "projeto__name"), ("provider", "provider__name"), ("uf", "uf"))}
