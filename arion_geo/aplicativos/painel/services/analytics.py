"""Analytics over the local CMDB and OTRS mirrors only."""
from collections import Counter, defaultdict
from datetime import date

from django.db.models import Count, Prefetch
from django.utils import timezone

from aplicativos.integracoes.models import OTRSTicketConfigItem, OTRSStateMapping
from aplicativos.integracoes.services.analytics import LinkQueryService, PeriodService, TicketQueryService

STATE_NAMES = {
    "AC": "Acre", "AL": "Alagoas", "AM": "Amazonas", "AP": "Amapá", "BA": "Bahia",
    "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás",
    "MA": "Maranhão", "MG": "Minas Gerais", "MS": "Mato Grosso do Sul", "MT": "Mato Grosso",
    "PA": "Pará", "PB": "Paraíba", "PE": "Pernambuco", "PI": "Piauí", "PR": "Paraná",
    "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RO": "Rondônia", "RR": "Roraima",
    "RS": "Rio Grande do Sul", "SC": "Santa Catarina", "SE": "Sergipe", "SP": "São Paulo", "TO": "Tocantins",
}
STATUS_ORDER = (
    OTRSStateMapping.BusinessStatus.OPEN,
    OTRSStateMapping.BusinessStatus.PENDING,
    OTRSStateMapping.BusinessStatus.RESOLVED,
    OTRSStateMapping.BusinessStatus.CLOSED,
    OTRSStateMapping.BusinessStatus.CANCELED,
    OTRSStateMapping.BusinessStatus.UNKNOWN,
)
MACRO_OPERATORS = (("VIVO", "vivo"), ("CLARO", "claro"), ("ALGAR", "algar"), ("OUTROS", "unclassified"))

METRICS = {
    "links": "Links CMDB", "tickets": "Tickets criados", "open_tickets": "Tickets abertos",
    "closed_tickets": "Tickets resolvidos/encerrados", "recurrences": "Links reincidentes",
    "backlog": "Backlog aberto",
}
DIMENSIONS = {"month": "M\u00eas", "operator": "Provedor", "project": "Projeto (legado)", "provider": "Provedor", "contract_operator": "Operadora", "uf": "UF", "status": "Status", "sla_status": "SLA", "service": "Servi\u00e7o"}
FILTERS = {"operator", "project", "provider", "contract_operator", "uf", "status", "sla_status", "service"}
LINK_DIMENSIONS = {"operator", "project", "provider", "contract_operator", "uf"}
OPEN = {OTRSStateMapping.BusinessStatus.OPEN, OTRSStateMapping.BusinessStatus.PENDING}
CLOSED = {OTRSStateMapping.BusinessStatus.RESOLVED, OTRSStateMapping.BusinessStatus.CLOSED, OTRSStateMapping.BusinessStatus.CANCELED}


def _months(start, end):
    result = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        result.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            month = 1
            year += 1
    return result


def _month_date(value):
    return PeriodService.parse_month(value)


class AnalyticsQueryService:
    def query(self, payload, user=None):
        metric = payload.get("metric", "tickets")
        group = payload.get("group_by", "operator")
        if metric not in METRICS or group not in DIMENSIONS or (metric == "links" and group not in LINK_DIMENSIONS | {"month"}):
            raise ValueError("Métrica ou dimensão não autorizada.")
        start, end = _month_date(payload.get("period_from")), _month_date(payload.get("period_to"))
        if start > end:
            raise ValueError("Período inicial posterior ao per\u00edodo final.")
        months = _months(start, end)
        selected = payload.get("period") or months[-1]
        if selected not in months:
            raise ValueError("Período selecionado fora do intervalo consultado.")
        compare = payload.get("compare_to")
        if compare:
            _month_date(compare)
        filters = payload.get("filters", {})
        if not isinstance(filters, dict) or set(filters) - FILTERS:
            raise ValueError("Filtro não autorizado.")
        links_qs = LinkQueryService.base(user)
        for key, field in (("operator", "operator__name"), ("project", "legacy_project"), ("provider", "operator__name"), ("uf", "state")):
            value = filters.get(key)
            if value not in (None, "", "all"):
                links_qs = links_qs.filter(**{field: value})
        links = list(links_qs.select_related("operator"))
        allowed_link_ids = {row.pk for row in links}
        relation_qs = OTRSTicketConfigItem.objects.filter(is_present_in_source=True, ticket__queue_name=TicketQueryService.QUEUE_NAME, ticket__is_present_in_queue=True, cmdb_link_id__in=allowed_link_ids).select_related("cmdb_link", "cmdb_link__operator")
        tickets_qs = TicketQueryService.base(user, links=links_qs).prefetch_related(Prefetch("config_items", queryset=relation_qs, to_attr="_scoped_relations"))
        if metric == "backlog":
            tickets_qs = tickets_qs.filter(is_business_open=True)
        tickets = list(tickets_qs)
        link_groups = defaultdict(set)
        month_rows = {month: [] for month in months}
        eligible_by_month = defaultdict(list)
        for ticket in tickets:
            related = [r for r in ticket._scoped_relations if r.cmdb_link_id in allowed_link_ids]
            link_objects = {r.cmdb_link_id: r.cmdb_link for r in related if r.cmdb_link_id}
            attrs = self._ticket_dimensions(ticket, link_objects.values())
            if not self._matches(attrs, filters):
                continue
            month = ticket.source_created_at.strftime("%Y-%m") if ticket.source_created_at else ""
            row = {"ticket": ticket, "links": list(link_objects.values()), "attrs": attrs}
            if month in month_rows:
                month_rows[month].append(row)
            if ticket.is_business_open:
                eligible_by_month["backlog"].append(row)
            for link in link_objects.values():
                link_groups[(month, link.pk)].add(ticket.pk)
        series = []
        for month in months:
            value = self._value(metric, month_rows[month], links, link_groups, month)
            series.append({"key": month, "label": self._label(month), "long_label": self._label(month, long=True), "value": value})
        current_rows = eligible_by_month["backlog"] if metric == "backlog" else month_rows[selected]
        current = self._value(metric, current_rows, links, link_groups, selected)
        previous = self._value(metric, month_rows.get(compare, []), links, link_groups, compare) if compare else None
        comparison = None if compare is None else {"value": previous, "difference": current-previous, "percent": round((current-previous)/previous*100,1) if previous else (0 if current == 0 else None), "direction": "neutral"}
        breakdown_rows = [row for month_rows_for_period in month_rows.values() for row in month_rows_for_period] if group == "month" else current_rows
        breakdown = self._breakdown(metric, group, breakdown_rows, links, link_groups, selected)
        detail_total = sum(value for _, value in breakdown)
        detail = [{"dimension": str(key), "value": value, "share": round(value/detail_total*100,1) if detail_total else 0} for key,value in breakdown]
        return {
            "metric": metric, "metric_label": METRICS[metric], "group_by": group, "group_by_label": DIMENSIONS[group],
            "source": "real", "period": selected, "period_from": months[0], "period_to": months[-1], "compare_to": compare,
            "value": current, "comparison": comparison, "series": series,
            "breakdown": [{"key": key, "value": value} for key,value in breakdown[:20]], "detail": detail[:100],
            "kpis": self._kpis(metric, current_rows, links, link_groups, selected),
            "provider_count": len({link.operator_id for link in links if link.operator_id}),
            "options": self._options(links, tickets), "meta": {"demo": False, "period_semantics": "source_created_at", "backlog_is_current_snapshot": True},
        }

    @staticmethod
    def _ticket_dimensions(ticket, links):
        links = list(links)
        return {
            "operator": {link.operator.name for link in links if link.operator and link.operator.name},
            "project": {link.legacy_project for link in links if link.legacy_project},
            "provider": {link.operator.name for link in links if link.operator and link.operator.name},
            "contract_operator": {"Operadora não classificada"} if links else set(),
            "uf": {link.state for link in links if link.state},
            "status": {ticket.business_status}, "sla_status": {ticket.sla_name} if ticket.sla_name else set(),
            "service": {ticket.service_name} if ticket.service_name else set(),
        }

    @staticmethod
    def _matches(attrs, filters):
        for key, value in filters.items():
            if value in (None, "", "all"):
                continue
            if value not in attrs.get(key, set()):
                return False
        return True

    @staticmethod
    def _value(metric, rows, links, link_groups, month):
        if metric == "links":
            return len(links)
        if metric == "tickets":
            return len({row["ticket"].pk for row in rows})
        if metric in ("open_tickets", "backlog"):
            return len({row["ticket"].pk for row in rows if row["ticket"].is_business_open})
        if metric == "closed_tickets":
            return len({row["ticket"].pk for row in rows if row["ticket"].business_status in CLOSED})
        return sum(1 for (row_month, _), ticket_ids in link_groups.items() if row_month == month and len(ticket_ids) >= 2)

    @classmethod
    def _breakdown(cls, metric, group, rows, links, link_groups, month):
        if metric == "links":
            if group == "month":
                return [("Link snapshot", len(links))]
            field = {"operator":"operator__name", "project":"legacy_project", "provider":"operator__name", "uf":"state"}.get(group)
            counts = Counter(str(getattr(link, field.split("__")[0]).name if "__" in field and getattr(link, field.split("__")[0]) else getattr(link, field or "state", "") or "Não classificado") for link in links)
            return sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold()))
        if group == "month":
            counts = Counter()
            if metric == "recurrences":
                for (row_month, _link_id), ticket_ids in link_groups.items():
                    if len(ticket_ids) >= 2:
                        counts[row_month] += 1
            else:
                ticket_ids_by_month = defaultdict(set)
                for row in rows:
                    key = row["ticket"].source_created_at.strftime("%Y-%m") if row["ticket"].source_created_at else "Sem data"
                    ticket_ids_by_month[key].add(row["ticket"].pk)
                counts.update({key: len(values) for key, values in ticket_ids_by_month.items()})
        elif group in LINK_DIMENSIONS:
            ticket_ids_by_dimension = defaultdict(set)
            for row in rows:
                for link in row["links"]:
                    value = {"operator": link.operator.name if link.operator else "N\u00e3o classificado", "project": link.legacy_project or "Projeto n\u00e3o classificado", "provider": link.operator.name if link.operator else "N\u00e3o classificado", "contract_operator": "Operadora n\u00e3o classificada", "uf": link.state or "N\u00e3o classificado"}[group]
                    ticket_ids_by_dimension[value or "N\u00e3o classificado"].add(row["ticket"].pk)
            counts = Counter({key: len(values) for key, values in ticket_ids_by_dimension.items()})
        else:
            counts = Counter()
            for row in rows:
                ticket = row["ticket"]
                value = {"status": ticket.business_status, "sla_status": ticket.sla_name or "Sem SLA", "service": ticket.service_name or "Sem serviço"}[group]
                counts[value] += 1
        if metric == "recurrences" and group in LINK_DIMENSIONS:
            counts = Counter()
            link_lookup = {link.pk: link for row in rows for link in row["links"]}
            for (row_month, link_id), ticket_ids in link_groups.items():
                if row_month != month or len(ticket_ids) < 2:
                    continue
                link = link_lookup.get(link_id)
                if not link:
                    continue
                value = {"operator": link.operator.name if link.operator else "N\u00e3o classificado", "project": link.legacy_project or "Projeto n\u00e3o classificado", "provider": link.operator.name if link.operator else "N\u00e3o classificado", "contract_operator": "Operadora n\u00e3o classificada", "uf": link.state or "N\u00e3o classificado"}[group]
                counts[value] += 1
        return sorted(counts.items(), key=lambda item: (-item[1], str(item[0]).casefold()))

    @classmethod
    def _kpis(cls, metric, rows, links, link_groups, month):
        tickets = {row["ticket"].pk: row["ticket"] for row in rows}
        open_count = sum(ticket.is_business_open for ticket in tickets.values())
        pending = sum(ticket.business_status == "PENDING" for ticket in tickets.values())
        affected = len({link.pk for row in rows if row["ticket"].is_business_open for link in row["links"]})
        if metric == "links":
            data = [("Links", len(links)), ("Provedores", len({link.operator_id for link in links if link.operator_id})), ("UFs", len({link.state for link in links if link.state})), ("Links com ticket aberto", affected)]
        elif metric == "backlog":
            data = [("Backlog atual", open_count), ("Abertos", open_count - pending), ("Pendentes", pending), ("Links afetados", affected)]
        else:
            data = [("Tickets no período", len(tickets)), ("Abertos + pendentes", open_count), ("Pendentes", pending), ("Links afetados", affected)]
        return [{"label": label, "value": value, "source": "real", "unit": ""} for label,value in data]

    @staticmethod
    def _options(links, tickets):
        result = {key: set() for key in ("operator", "project", "provider", "contract_operator", "uf", "status", "sla_status", "service")}
        for link in links:
            for key,value in (("operator",link.operator.name if link.operator else ""),("project",link.legacy_project),("provider",link.operator.name if link.operator else ""),("contract_operator","Operadora não classificada"),("uf",link.state)):
                if value: result[key].add(value)
        for ticket in tickets:
            result["status"].add(ticket.business_status)
            if ticket.sla_name: result["sla_status"].add(ticket.sla_name)
            if ticket.service_name: result["service"].add(ticket.service_name)
        return {key: sorted(values) for key,values in result.items()}

    @staticmethod
    def _label(month, long=False):
        year, number = map(int, month.split("-"))
        names = ("Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez")
        return f"{names[number-1]} de {year}" if long else f"{names[number-1]}/{str(year)[-2:]}"

    def dashboard_snapshot(self, user=None):
        return {"monthly": [], "calls": 0, "repeat": 0}


class DashboardAnalyticsService:
    """Build the executive Dashboard from scoped local CMDB and NOC mirrors."""

    @staticmethod
    def build(*, user, start, end):
        from datetime import date, datetime, time, timedelta

        from django.db.models.functions import TruncMonth

        links = LinkQueryService.base(user)
        tickets = TicketQueryService.base(user, links=links)
        local_tz = timezone.get_current_timezone()
        start_at = timezone.make_aware(datetime.combine(start, time.min), local_tz)
        end_at = timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min), local_tz)
        period_tickets = tickets.filter(source_created_at__gte=start_at, source_created_at__lt=end_at)
        current_tickets = tickets.filter(is_present_in_queue=True)
        business_open = current_tickets.filter(is_business_open=True)

        total_links = links.count()
        state_rows = list(
            links.filter(state__in=STATE_NAMES)
            .values("state").annotate(value=Count("pk"))
            .order_by("-value", "state")
        )
        top_states = [
            {"code": row["state"], "name": STATE_NAMES[row["state"]], "value": row["value"],
             "flag": f"imagens/bandeiras/estados/{row['state'].lower()}.svg"}
            for row in state_rows[:10]
        ]

        # This frozen classification is separate from the current local ISP.
        macro_rows = links.values("legacy_operator_classification").annotate(value=Count("pk"))
        macro_counts = {}
        for row in macro_rows:
            classification = row["legacy_operator_classification"]
            group = classification if classification in {"VIVO", "CLARO", "ALGAR"} else "OUTROS"
            macro_counts[group] = macro_counts.get(group, 0) + row["value"]
        macro_operators = [
            {"name": name, "key": key, "value": macro_counts.get(name, 0),
             "share": round(macro_counts.get(name, 0) / total_links * 100, 1) if total_links else 0}
            for name, key in MACRO_OPERATORS
        ]
        macro_classified = sum(macro_counts.get(name, 0) for name in ("VIVO", "CLARO", "ALGAR"))

        snapshot_status = {row["business_status"]: row["total"] for row in current_tickets.values(
            "business_status"
        ).annotate(total=Count("pk"))}
        status_counts = {status: snapshot_status.get(status, 0) for status in STATUS_ORDER}
        open_count = status_counts[OTRSStateMapping.BusinessStatus.OPEN]
        pending_count = status_counts[OTRSStateMapping.BusinessStatus.PENDING]

        current_relations = OTRSTicketConfigItem.objects.filter(
            is_present_in_source=True,
            ticket__queue_name=TicketQueryService.QUEUE_NAME,
            ticket__is_present_in_queue=True,
            ticket__is_business_open=True,
            cmdb_link__in=links,
        )
        links_affected = current_relations.values("cmdb_link_id").distinct().count()

        calls = period_tickets.count()
        recurrence_base = OTRSTicketConfigItem.objects.filter(
            is_present_in_source=True,
            ticket__queue_name=TicketQueryService.QUEUE_NAME,
            ticket__is_present_in_queue=True,
            ticket__source_created_at__gte=start_at,
            ticket__source_created_at__lt=end_at,
            cmdb_link__in=links,
        )
        recurrence_total = recurrence_base.values("cmdb_link_id").annotate(
            ticket_count=Count("ticket_id", distinct=True),
        ).filter(ticket_count__gte=2).count()

        calls_by_month = {
            (row["month"].year, row["month"].month): row["total"]
            for row in period_tickets.annotate(month=TruncMonth("source_created_at"))
            .values("month").annotate(total=Count("pk"))
        }
        recurring_by_month = {}
        recurring_month_links = (
            recurrence_base.annotate(month=TruncMonth("ticket__source_created_at"))
            .values("month", "cmdb_link_id")
            .annotate(ticket_count=Count("ticket_id", distinct=True))
            .filter(ticket_count__gte=2)
        )
        for row in recurring_month_links:
            key = (row["month"].year, row["month"].month)
            recurring_by_month[key] = recurring_by_month.get(key, 0) + 1

        monthly = []
        year, month = start.year, start.month
        while (year, month) <= (end.year, end.month):
            month_start = date(year, month, 1)
            month_label = month_start.strftime("%b")
            monthly.append({
                "month": month_label,
                "label": f"{month_label}/{str(year)[-2:]}",
                "calls": calls_by_month.get((year, month), 0),
                "repeat": recurring_by_month.get((year, month), 0),
            })
            month += 1
            if month == 13:
                year, month = year + 1, 1

        return {
            "total_links": total_links,
            "state_count": len(state_rows),
            "top_states": top_states,
            "macro_operators": macro_operators,
            "macro_operator_coverage": round(macro_classified / total_links * 100, 1) if total_links else 0,
            "calls": calls,
            "repeat": recurrence_total,
            "business_open": business_open.count(),
            "open_count": open_count,
            "pending_count": pending_count,
            "resolved_count": status_counts[OTRSStateMapping.BusinessStatus.RESOLVED],
            "closed_count": status_counts[OTRSStateMapping.BusinessStatus.CLOSED],
            "canceled_count": status_counts[OTRSStateMapping.BusinessStatus.CANCELED],
            "unknown_count": status_counts[OTRSStateMapping.BusinessStatus.UNKNOWN],
            "links_affected": links_affected,
            "monthly": monthly,
        }
