"""Analytics over the local CMDB and OTRS mirrors only."""
import calendar
from datetime import date, datetime, time, timedelta, timezone as datetime_timezone
import unicodedata
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Case, CharField, Count, Value, When

from aplicativos.integracoes.models import OTRSTicket, OTRSTicketConfigItem, OTRSStateMapping
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
    OTRSStateMapping.BusinessStatus.SCHEDULED,
    OTRSStateMapping.BusinessStatus.RESOLVED,
    OTRSStateMapping.BusinessStatus.CLOSED,
    OTRSStateMapping.BusinessStatus.CANCELED,
    OTRSStateMapping.BusinessStatus.UNKNOWN,
)

def normalize_closing_reason(value):
    raw = str(value or "").strip()
    normalized = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode().casefold()
    if normalized in {"pendenciafinanceira", "pendencia financeira"}:
        return "Pendência Financeira"
    return raw or "Não classificado"

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


def _date_boundaries(start, end, tz=None):
    """Build local calendar bounds and return UTC instants for DB comparisons."""
    zone = tz or ZoneInfo(settings.TIME_ZONE)
    start_local = datetime.combine(start, time.min, tzinfo=zone)
    end_exclusive_local = datetime.combine(end + timedelta(days=1), time.min, tzinfo=zone)
    return (start_local.astimezone(datetime_timezone.utc),
            end_exclusive_local.astimezone(datetime_timezone.utc))


def _month_buckets(start, end, tz=None):
    zone = tz or ZoneInfo(settings.TIME_ZONE)
    cursor = start.replace(day=1)
    last = end.replace(day=1)
    buckets = []
    while cursor <= last:
        next_month = date(cursor.year + (cursor.month == 12), 1 if cursor.month == 12 else cursor.month + 1, 1)
        local_start = datetime.combine(cursor, time.min, tzinfo=zone)
        local_end = datetime.combine(next_month, time.min, tzinfo=zone)
        buckets.append((cursor.strftime("%Y-%m"), local_start.astimezone(datetime_timezone.utc),
                        local_end.astimezone(datetime_timezone.utc)))
        cursor = next_month
    return buckets


def _month_case(field, buckets):
    return Case(*[
        When(**{f"{field}__gte": start, f"{field}__lt": end}, then=Value(key))
        for key, start, end in buckets
    ], default=Value(None), output_field=CharField(max_length=7))


def _time_buckets(start, end, tz=None):
    days = (end - start).days + 1
    if days <= 31:
        grain = "day"
    elif days <= 90:
        grain = "week"
    else:
        grain = "month"
    zone = tz or ZoneInfo(settings.TIME_ZONE)
    buckets = []
    if grain == "day":
        cursor = start
        while cursor <= end:
            following = cursor + timedelta(days=1)
            key = cursor.isoformat()
            label = f"{cursor.day:02d} {('Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez')[cursor.month - 1]}"
            buckets.append((key, label, datetime.combine(cursor, time.min, tzinfo=zone).astimezone(datetime_timezone.utc),
                            datetime.combine(following, time.min, tzinfo=zone).astimezone(datetime_timezone.utc)))
            cursor = following
    elif grain == "week":
        cursor = start - timedelta(days=start.weekday())
        names = ('Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez')
        while cursor <= end:
            following = cursor + timedelta(days=7)
            week_end = following - timedelta(days=1)
            label = f"{cursor.day:02d} {names[cursor.month - 1]}–{week_end.day:02d} {names[week_end.month - 1]}"
            key = f"{cursor.isocalendar().year}-W{cursor.isocalendar().week:02d}"
            buckets.append((key, label, datetime.combine(cursor, time.min, tzinfo=zone).astimezone(datetime_timezone.utc),
                            datetime.combine(following, time.min, tzinfo=zone).astimezone(datetime_timezone.utc)))
            cursor = following
    else:
        for key, bucket_start, bucket_end in _month_buckets(start, end, zone):
            buckets.append((key, AnalyticsQueryService._month_label(key), bucket_start, bucket_end))
    return grain, buckets


def _period_case(field, buckets):
    return Case(*[
        When(**{f"{field}__gte": start, f"{field}__lt": end}, then=Value(key))
        for key, _label, start, end in buckets
    ], default=Value(None), output_field=CharField(max_length=10))


class AnalyticsQueryService:
    """Ticket analytics constrained to the scoped, current NOC queue mirror."""

    OPERATIONAL_VALID_STATES = ("OPEN", "PENDING", "SCHEDULED", "RESOLVED", "CLOSED")

    METRICS = {
        "tickets": "Tickets criados",
        "open_tickets": "Em atendimento",
        "pending_tickets": "Pendentes",
        "scheduled_tickets": "Agendados",
        "resolved_tickets": "Resolvidos no per\u00edodo",
        "closed_tickets": "Encerrados no per\u00edodo",
        "resolved_closed_tickets": "Resolvidos + Encerrados",
        "canceled_tickets": "Cancelados no per\u00edodo",
        "links_affected": "Links afetados no per\u00edodo",
        "recurrences": "Links reincidentes",
        "backlog": "Backlog atual",
    }
    DIMENSIONS = {
        "provider": "Provedor",
        "uf": "UF",
        "status": "Status",
        "source_state": "Situa\u00e7\u00e3o OTRS",
        "priority": "Prioridade",
        "termination_reason": "Motivo de encerramento",
        "sla": "SLA",
        "month": "Per\u00edodo",
    }
    FILTERS = {"provider", "uf", "status", "source_state", "service", "sla", "priority", "termination_reason"}
    LINK_FILTERS = {
        "provider": "config_items__cmdb_link__operator__name",
        "uf": "config_items__cmdb_link__state",
    }
    LINK_GROUPS = {
        "provider": "config_items__cmdb_link__operator__name",
        "uf": "config_items__cmdb_link__state",
    }
    STATUS_LABELS = {
        "OPEN": "Em atendimento",
        "PENDING": "Pendente",
        "SCHEDULED": "Agendado",
        "RESOLVED": "Resolvido",
        "CLOSED": "Encerrado",
        "CANCELED": "Cancelado",
        "UNKNOWN": "Não classificado",
    }
    SOURCE_STATE_LABELS = {
        "em atendimento": "Em atendimento",
        "pendente": "Pendente",
        "agendado": "Agendado",
        "resolvido": "Resolvido",
        "closed successful": "Encerrado com sucesso",
        "encerrado com viabilidade": "Encerrado com viabilidade",
        "cancelado": "Cancelado",
    }
    METRIC_STATUS = {
        "open_tickets": "OPEN",
        "pending_tickets": "PENDING",
        "scheduled_tickets": "SCHEDULED",
        "resolved_tickets": "RESOLVED",
        "closed_tickets": "CLOSED",
        "canceled_tickets": "CANCELED",
    }
    LEGACY_FILTERS = {"operator": "provider", "sla_status": "sla", "contract_operator": None}
    LEGACY_DIMENSIONS = {"operator": "provider", "project": "provider", "service": "provider", "sla_status": "sla", "contract_operator": None, "isp": None}

    FILTER_ALIASES = {"closing_reason": "termination_reason", "closing_code_raw": "termination_reason"}
    SNAPSHOT_METRICS = {"backlog"}

    def query(self, payload, user=None, *, include_all_rows=False):
        from django.db.models import Count

        query = self.normalize_query(payload)
        metric, group = query["metric"], query["group_by"]
        start, end, filters = query["start"], query["end"], query["filters"]
        start_at, end_exclusive = _date_boundaries(start, end)
        grain, buckets = _time_buckets(start, end)

        # Scope is applied before user filters, counts, groups, pagination, and export.
        allowed_links = LinkQueryService.base(user)
        noc_tickets = TicketQueryService.base(user, links=allowed_links).order_by()
        metric_universe = self._metric_universe(noc_tickets, metric)
        options = self._options(metric_universe, allowed_links)
        filtered = self._apply_filters(metric_universe, allowed_links, filters)
        date_field = self._metric_date_field(metric)
        if metric in self.SNAPSHOT_METRICS:
            temporal_rows = filtered
        else:
            temporal_rows = filtered.filter(**{f"{date_field}__gte": start_at,
                                               f"{date_field}__lt": end_exclusive})
        analysis_rows = self._metric_rows(filtered, temporal_rows, metric)
        selected_value = self._metric_value(analysis_rows, metric, allowed_links)
        comparison = self._comparison(filtered, query, allowed_links, selected_value)
        series = self._series(analysis_rows, metric, buckets, allowed_links, selected_value)
        temporal = self._monthly_calendar(
            analysis_rows, metric, start, end, query["selected_month"], series, allowed_links,
        )
        grouped = self._grouped(analysis_rows, metric, group, allowed_links, buckets)
        provider_quality = self._provider_quality(analysis_rows, allowed_links)
        bucket_labels = {key: label for key, label, _start, _end in buckets}

        total_rows = len(grouped) if isinstance(grouped, list) else grouped.count()
        page_size = 25
        try:
            requested_page = max(1, int(payload.get("detail_page", 1)))
        except (TypeError, ValueError):
            requested_page = 1
        page_count = max(1, (total_rows + page_size - 1) // page_size)
        current_page = min(requested_page, page_count)
        if include_all_rows:
            detail_rows = list(grouped)
        else:
            offset = (current_page - 1) * page_size
            detail_rows = list(grouped[offset:offset + page_size])
        denominator = (provider_quality["identified"] if group == "provider" and metric not in {"links_affected", "recurrences"}
                       else selected_value) or 0

        def present(row):
            raw = row["dimension"] if row["dimension"] not in (None, "") else "N\u00e3o classificado"
            label = bucket_labels.get(raw, raw) if group == "month" else self._dimension_label(group, raw)
            return {"key": str(raw), "dimension": label, "value": row["value"],
                    "share": round(row["value"] / denominator * 100, 1) if denominator else 0}

        detail = [present(row) for row in detail_rows]
        top = [present(row) for row in list(grouped[:10])]
        context = self._context_kpis(metric, selected_value, analysis_rows, provider_quality)
        description = self._query_description(metric, group, filters, start, end)
        previous_quality = comparison.pop("provider_quality", None) if comparison else None
        previous_series = comparison.pop("previous_series", []) if comparison else []
        previous_grouped = comparison.pop("previous_grouped", []) if comparison else []
        self._add_kpi_trends(context["kpis"], comparison, previous_quality)
        chart_specs = self._chart_specs(
            metric, group, filters, series, top, grain, selected_value,
            previous_series, previous_grouped, rows=analysis_rows, links=allowed_links,
        )
        if temporal:
            chart_specs.insert(1, temporal.pop("chart_spec"))
        ticket_data = self._ticket_results(
            analysis_rows, allowed_links, payload, include_all_rows=include_all_rows,
            metric=metric, filters=filters, start=start, end=end, user=user, group=group,
        )
        period_status_counts = {
            row["business_status"]: row["total"]
            for row in temporal_rows.values("business_status").annotate(total=Count("pk", distinct=True))
        }
        period_from = start.strftime("%Y-%m")
        period_to = end.strftime("%Y-%m")
        return {
            "metric": metric, "metric_label": self.METRICS[metric],
            "group_by": group, "group_by_label": self.DIMENSIONS[group],
            "source": "real", "period": period_to, "period_from": period_from,
            "period_to": period_to, "start_date": start.isoformat(), "end_date": end.isoformat(),
            "compare_to": query["compare_to"], "value": selected_value,
            "comparison": comparison, "series": series, "breakdown": top,
            "provider_ranking": top if group == "provider" else [],
            "detail": detail, "detail_page": current_page,
            "detail_page_size": page_size, "detail_total": total_rows,
            "detail_pages": page_count, "kpis": context["kpis"],
            "provider_quality": provider_quality,
            "chart_specs": chart_specs,
            "time_grain": grain,
            "temporal": temporal,
            "description": description,
            **ticket_data,
            "period_status_counts": period_status_counts,
            "metric_semantics": self._metric_semantics(metric),
            "period_date_label": ("snapshot atual" if metric == "backlog"
                                  else "data de encerramento" if metric in {"resolved_tickets", "closed_tickets", "resolved_closed_tickets"}
                                  else "data de cancelamento" if metric == "canceled_tickets"
                                  else "data de cria\u00e7\u00e3o"),
            "provider_count": len(options["provider"]), "options": options,
            "normalized_query": {"metric": metric, "start": start.isoformat(), "end": end.isoformat(),
                                 "group_by": group, "filters": filters,
                                 "selected_month": temporal["selected_month"] if temporal else None},
            "meta": {"demo": False, "period_semantics": date_field,
                     "backlog_is_current_snapshot": metric in self.SNAPSHOT_METRICS,
                     "operational_valid_states": self.OPERATIONAL_VALID_STATES,
                     "excluded_by_default": ("CANCELED", "UNKNOWN"),
                     "ticket_totals_are_distinct": True,
                     "provider_groups_can_count_one_ticket_in_multiple_providers": True,
                     "termination_reason_available": True},
        }

    @classmethod
    def _metric_universe(cls, scoped_tickets, metric):
        if metric == "canceled_tickets":
            return scoped_tickets.filter(business_status="CANCELED")
        return scoped_tickets.filter(business_status__in=cls.OPERATIONAL_VALID_STATES)

    @classmethod
    def _provider_quality(cls, rows, links):
        from django.db.models import Count, Exists, OuterRef
        from aplicativos.integracoes.models import OTRSTicketConfigItem

        total = rows.values("pk").distinct().count()
        relations = OTRSTicketConfigItem.objects.filter(
            ticket_id=OuterRef("pk"), is_present_in_source=True,
        )
        valid_link = relations.filter(cmdb_link__is_present_in_source=True, cmdb_link__in=links)
        valid_provider = valid_link.filter(cmdb_link__operator__isnull=False).exclude(cmdb_link__operator__name="")
        classified_ids = OTRSTicketConfigItem.objects.filter(
            ticket_id__in=rows.values("pk"), is_present_in_source=True,
            cmdb_link__is_present_in_source=True, cmdb_link__in=links,
        ).exclude(cmdb_link__operator__isnull=True).exclude(cmdb_link__operator__name="").values("ticket_id")
        identified = rows.filter(pk__in=classified_ids).values("pk").distinct().count()
        unclassified = max(total - identified, 0)
        quality_rows = rows.annotate(
            _has_relation=Exists(relations),
            _has_link=Exists(relations.filter(cmdb_link__isnull=False)),
            _has_valid_link=Exists(valid_link),
            _has_provider=Exists(valid_provider),
        )
        unresolved = quality_rows.filter(_has_provider=False)
        causes = {
            "no_config_item": unresolved.filter(_has_relation=False).values("pk").distinct().count(),
            "missing_mirror": unresolved.filter(_has_relation=True, _has_link=False).values("pk").distinct().count(),
            "invalid_link": unresolved.filter(_has_link=True, _has_valid_link=False).values("pk").distinct().count(),
            "link_without_provider": unresolved.filter(_has_valid_link=True).values("pk").distinct().count(),
        }
        provider_groups = OTRSTicketConfigItem.objects.filter(
            ticket_id__in=rows.values("pk"), is_present_in_source=True,
            cmdb_link__is_present_in_source=True, cmdb_link__in=links,
        ).exclude(cmdb_link__operator__isnull=True).exclude(cmdb_link__operator__name="").values(
            "cmdb_link__operator__name",
        ).annotate(value=Count("ticket_id", distinct=True)).order_by("-value", "cmdb_link__operator__name")
        top = next(iter(provider_groups), None)
        return {
            "total": total, "identified": identified, "unresolved": unclassified,
            "coverage_percent": round(identified * 100 / total, 1) if total else 0,
            "unresolved_causes": causes,
            "top_provider": ({"name": top["cmdb_link__operator__name"], "value": top["value"]} if top else None),
            "provider_groups_can_overlap": True,
        }

    @classmethod
    def _context_kpis(cls, metric, total, rows, provider_quality):
        from django.db.models import Count, Q

        if metric == "backlog":
            counts = rows.aggregate(
                open=Count("pk", filter=Q(business_status="OPEN"), distinct=True),
                pending=Count("pk", filter=Q(business_status="PENDING"), distinct=True),
                scheduled=Count("pk", filter=Q(business_status="SCHEDULED"), distinct=True),
            )
            return {"kpis": [
                {"key": "total", "label": "Backlog total", "value": total, "unit": "Em atendimento + Pendente + Agendado"},
                {"label": "Em atendimento", "value": counts["open"], "unit": ""},
                {"label": "Pendentes", "value": counts["pending"], "unit": ""},
                {"label": "Agendados", "value": counts["scheduled"], "unit": ""},
            ]}
        if metric in {"links_affected", "recurrences"}:
            return {"kpis": [{"key": "total", "label": cls.METRICS[metric], "value": total, "unit": ""}]}
        return {"kpis": [
            {"key": "total", "label": "Tickets encontrados" if metric == "tickets" else cls.METRICS[metric],
             "value": total, "unit": "Criados no per\u00edodo conforme os filtros ativos" if metric == "tickets" else ""},
            {"key": "identified", "label": "Com provedor identificado", "value": provider_quality["identified"], "unit": ""},
            {"key": "unresolved", "label": "Sem provedor identificado", "value": provider_quality["unresolved"], "unit": ""},
            {"key": "coverage", "label": "Cobertura de provedor", "value": provider_quality["coverage_percent"], "unit": "% dos tickets"},
        ]}

    @staticmethod
    def _add_kpi_trends(kpis, comparison, previous_quality):
        if not comparison:
            return
        previous = {"total": comparison["previous_value"]}
        if previous_quality:
            previous.update({"identified": previous_quality["identified"],
                             "unresolved": previous_quality["unresolved"],
                             "coverage": previous_quality["coverage_percent"]})
        for item in kpis:
            key = item.get("key")
            if key not in previous:
                continue
            current, before = item["value"], previous[key]
            change = current - before
            percentage = round(change * 100 / before, 1) if before else (0 if not change else None)
            item["trend"] = {
                "current_value": current, "previous_value": before,
                "absolute_change": round(change, 1) if key == "coverage" else change,
                "percentage_change": percentage,
                "direction": "up" if change > 0 else "down" if change < 0 else "neutral",
                "unit": "p.p." if key == "coverage" else "",
                "favorable": (change > 0 if key == "coverage" else change < 0 if key == "unresolved" else None),
            }

    @staticmethod
    def _previous_period(start, end):
        if start.day == 1 and end == AnalyticsQueryService._month_end(end):
            previous_end = start - timedelta(days=1)
            previous_start = previous_end.replace(day=1)
            return previous_start, previous_end
        length = (end - start).days + 1
        previous_end = start - timedelta(days=1)
        return previous_end - timedelta(days=length - 1), previous_end

    @classmethod
    def _query_description(cls, metric, group, filters, start, end):
        fmt = lambda value: value.strftime("%d/%m/%Y")
        period = f"{fmt(start)} a {fmt(end)}"
        reason = filters.get("termination_reason")
        if metric == "backlog":
            title = f"Backlog atual por {cls.DIMENSIONS[group].lower()}"
            subtitle = "Fila atual: em atendimento, pendente ou agendada"
            period = "Atual"
        elif reason and metric == "tickets":
            title = f"An\u00e1lise de {reason}"
            subtitle = f"Tickets v\u00e1lidos criados entre {fmt(start)} e {fmt(end)} conforme os filtros ativos"
        elif reason:
            metric_word = {"closed_tickets": "encerrados", "resolved_tickets": "resolvidos",
                           "resolved_closed_tickets": "resolvidos e encerrados", "canceled_tickets": "cancelados"}.get(
                               metric, cls.METRICS[metric].lower())
            title = f"Tickets {metric_word} por {reason}"
            subtitle = f"{fmt(start)} a {fmt(end)}"
        else:
            metric_word = cls.METRICS[metric].lower()
            title = f"An\u00e1lise de {metric_word}"
            subtitle = f"{fmt(start)} a {fmt(end)}"
        return {"title": title, "subtitle": subtitle, "period": period,
                "metric_label": cls.METRICS[metric], "group_label": cls.DIMENSIONS[group]}

    @staticmethod
    def _ticket_pagination(payload):
        try:
            page = max(1, int(payload.get("ticket_page", 1)))
            size = int(payload.get("ticket_page_size", 25))
        except (TypeError, ValueError):
            page, size = 1, 25
        return page, size if size in {25, 50, 100} else 25

    @classmethod
    def _ticket_results(cls, rows, links, payload, *, include_all_rows, metric, filters, start, end, user, group):
        from django.db.models import Prefetch, Q
        from django.utils import timezone

        page, page_size = cls._ticket_pagination(payload)
        search = str(payload.get("ticket_search") or "").strip()[:120]
        ticket_day = str(payload.get("ticket_day") or "").strip()
        day_rows = rows
        if ticket_day:
            try:
                selected_day = date.fromisoformat(ticket_day)
            except ValueError:
                raise ValueError("Data do ticket inv\u00e1lida.") from None
            if metric in cls.SNAPSHOT_METRICS or not start <= selected_day <= end:
                raise ValueError("O dia selecionado est\u00e1 fora da an\u00e1lise atual.")
            day_start, day_end = _date_boundaries(selected_day, selected_day)
            date_field = cls._metric_date_field(metric)
            day_rows = rows.filter(**{f"{date_field}__gte": day_start, f"{date_field}__lt": day_end})
        tickets = day_rows.order_by()
        if search:
            relation_search = Q(config_items__is_present_in_source=True, config_items__cmdb_link__in=links)
            if user is None or getattr(user, "is_superuser", False):
                relation_search |= Q(config_items__is_present_in_source=True, config_items__cmdb_link__isnull=True)
            tickets = tickets.filter(
                Q(ticket_number__icontains=search)
                | (relation_search & Q(config_items__config_item_id__icontains=search))
                | (relation_search & Q(config_items__cmdb_link__source_number__icontains=search))
                | (relation_search & Q(config_items__cmdb_link__name__icontains=search))
                | (relation_search & Q(config_items__cmdb_link__designation__icontains=search))
                | (relation_search & Q(config_items__cmdb_link__circuit__icontains=search))
                | (relation_search & Q(config_items__cmdb_link__operator__name__icontains=search))
            ).distinct()
        result_count = rows.values("pk").distinct().count()
        found_count = tickets.values("pk").distinct().count()
        page_count = max(1, (found_count + page_size - 1) // page_size)
        page = min(page, page_count)
        relation_qs = OTRSTicketConfigItem.objects.filter(is_present_in_source=True)
        if user is not None and not getattr(user, "is_superuser", False):
            relation_qs = relation_qs.filter(cmdb_link__in=links)
        else:
            relation_qs = relation_qs.filter(Q(cmdb_link__in=links) | Q(cmdb_link__isnull=True))
        relation_qs = relation_qs.select_related("cmdb_link__operator").order_by("pk")
        prefetch = Prefetch("config_items", queryset=relation_qs, to_attr="_cockpit_relations")
        date_field = cls._metric_date_field(metric)
        tickets = tickets.order_by(f"-{date_field}", "-pk").prefetch_related(prefetch)
        selection = tickets if include_all_rows else tickets[(page - 1) * page_size:page * page_size]
        rows_json = [cls._present_ticket(ticket, metric, filters, start, end, timezone, ticket_day=ticket_day) for ticket in selection]
        return {"tickets": rows_json, "ticket_total": found_count, "ticket_result_total": result_count,
                "ticket_page": page, "ticket_page_size": page_size, "ticket_pages": page_count,
                "ticket_search": search, "ticket_day": ticket_day or None,
                "ticket_day_total": day_rows.values("pk").distinct().count() if ticket_day else None}

    @classmethod
    def _present_ticket(cls, ticket, metric, filters, start, end, timezone, *, ticket_day=None):
        def stamp(value):
            return timezone.localtime(value).strftime("%d/%m/%Y %H:%M") if value else "—"
        relations = []
        providers, states = set(), set()
        for relation in getattr(ticket, "_cockpit_relations", []):
            link = relation.cmdb_link
            detail = {"config_item_id": relation.config_item_id, "resolved": bool(link), "number": link.source_number if link else "",
                      "designation": link.designation if link else "", "circuit": link.circuit if link else "",
                      "provider": link.operator.name if link and link.operator else "", "uf": link.state if link else ""}
            relations.append(detail)
            if detail["provider"]: providers.add(detail["provider"])
            if detail["uf"]: states.add(detail["uf"])
        status = cls.STATUS_LABELS.get(ticket.business_status, ticket.business_status)
        reason = normalize_closing_reason(ticket.closing_code_raw)
        date_field = cls._metric_date_field(metric)
        base_labels = {
            "tickets": "Criado entre", "open_tickets": "Criado entre", "pending_tickets": "Criado entre",
            "scheduled_tickets": "Criado entre", "resolved_tickets": "Data de encerramento entre",
            "closed_tickets": "Data de encerramento entre", "resolved_closed_tickets": "Data terminal entre",
            "canceled_tickets": "Cancelado entre",
        }
        base_evidence = (f"{base_labels.get(metric, 'Data base entre')} {start:%d/%m/%Y} e {end:%d/%m/%Y}"
                         if metric != "backlog" else "Ticket presente no backlog atual")
        evidence = [base_evidence, f"Estado atual: {status}"]
        if ticket_day:
            evidence.append(f"Dia selecionado na an\u00e1lise: {date.fromisoformat(ticket_day):%d/%m/%Y}")
        if metric == "canceled_tickets":
            evidence.append("M\u00e9trica espec\u00edfica de cancelamentos")
        elif metric in {"resolved_tickets", "closed_tickets", "resolved_closed_tickets"}:
            evidence.append(f"Data terminal e estado correspondente: {status}")
        if ticket.business_status in cls.OPERATIONAL_VALID_STATES:
            evidence.append("Estado operacional v\u00e1lido")
        for key, value in filters.items():
            if key == "termination_reason": evidence.append(f"Motivo = {reason}")
            elif key == "provider" and value in providers: evidence.append(f"Provedor = {value}")
            elif key == "uf" and value in states: evidence.append(f"UF = {value}")
            elif key == "status" and value == ticket.business_status: evidence.append(f"Status = {status}")
            elif key == "source_state" and value == ticket.external_state_name: evidence.append(f"Situa\u00e7\u00e3o OTRS = {ticket.external_state_name}")
            elif key == "priority" and value == ticket.priority_name: evidence.append(f"Prioridade = {ticket.priority_name}")
            elif key == "priority" and value == "high-critical":
                normalized_priority = unicodedata.normalize("NFKD", ticket.priority_name).encode("ascii", "ignore").decode().casefold()
                if normalized_priority in {"alto", "critico"}: evidence.append("Prioridade = Alto / Cr\u00edtico")
            elif key == "sla" and value == ticket.sla_name: evidence.append(f"SLA = {ticket.sla_name}")
            elif key == "service" and value == ticket.service_name: evidence.append(f"Servi\u00e7o = {ticket.service_name}")
        evidence.append("Dentro do Data Scope aplicado")
        has_link = any(item["resolved"] for item in relations)
        base_date = "Atual" if metric == "backlog" else stamp(getattr(ticket, date_field))
        return {"id": ticket.pk, "ticket": ticket.ticket_number, "base_date": base_date,
                "created_at": stamp(ticket.source_created_at), "changed_at": stamp(ticket.source_changed_at),
                "terminal_at": stamp(ticket.terminal_state_at), "resolved_at": stamp(ticket.resolved_at),
                "canceled_at": stamp(ticket.canceled_at), "status": status, "status_code": ticket.business_status,
                "source_state": ticket.external_state_name, "reason": reason,
                "provider": ", ".join(sorted(providers)) or "N\u00e3o identificado", "uf": ", ".join(sorted(states)),
                "priority": ticket.priority_name, "sla": ticket.sla_name, "service": ticket.service_name,
                "source": "OTRS + CMDB" if has_link else "OTRS", "links": relations, "evidence": evidence}

    @classmethod
    def _chart_specs(cls, metric, group, filters, series, grouped, grain, total,
                     previous_series=(), previous_grouped=(), *, rows=None, links=None):
        specs = []
        prior_time = [row["value"] for row in previous_series]
        if metric not in cls.SNAPSHOT_METRICS:
            grain_label = {"day": "di\u00e1ria", "week": "semanal", "month": "mensal"}[grain]
            values = [row["value"] for row in series]
            if len(set(values)) > 1:
                base_label = {"source_created_at": "data de cria\u00e7\u00e3o", "terminal_state_at": "data de encerramento",
                              "canceled_at": "data de cancelamento"}.get(cls._metric_date_field(metric), "data de cria\u00e7\u00e3o")
                specs.append({"key": "temporal", "type": "temporal_overview", "grain": grain,
                              "title": "Vis\u00e3o geral do per\u00edodo",
                              "subtitle": f"Granularidade {grain_label} \u00b7 Base temporal: {base_label}",
                              "dimension": "time", "metric": metric, "unit": cls._chart_unit(metric),
                              "labels": [row["label"] for row in series], "values": values,
                              "details": [{"key": row["key"], "label": row.get("long_label", row["label"]), "value": row["value"],
                                           "share": round(row["value"] * 100 / total, 1) if total else 0,
                                           "previous_value": prior_time[index] if index < len(prior_time) else None}
                                          for index, row in enumerate(series)]})
        fixed = {"provider": "provider", "uf": "uf", "status": "status", "source_state": "source_state",
                 "priority": "priority", "sla": "sla", "termination_reason": "termination_reason"}
        def dimension_spec(dimension, dimension_rows, *, complementary=False):
            denominator = total
            if dimension == "provider" and metric not in {"links_affected", "recurrences"} and not dimension_rows[0].get("share"):
                denominator = cls._provider_quality(rows, links)["identified"] if rows is not None else total
            entries = []
            for row in dimension_rows[:10]:
                raw = row.get("dimension", "")
                label = cls._dimension_label(dimension, raw)
                value = row["value"]
                entries.append({"key": str(raw), "label": label, "value": value,
                                "share": row.get("share", round(value * 100 / denominator, 1) if denominator else 0),
                                "previous_value": next((item["value"] for item in previous_grouped if item["label"] == label), None)
                                if not complementary and dimension == group else None})
            if not entries:
                return None
            title = ("Ranking de provedores" if dimension == "provider" else "Ranking de UFs") if dimension in {"provider", "uf"} else f"Distribui\u00e7\u00e3o por {cls.DIMENSIONS[dimension].lower()}"
            chart_type = "ranking" if dimension in {"provider", "uf"} else "compact_distribution" if dimension == "status" else "horizontal_bar"
            subtitle = ("Participa\u00e7\u00e3o sobre tickets com provedor identificado" if dimension == "provider"
                        else cls.METRICS[metric])
            spec_key = "provider-ranking" if dimension == "provider" else "uf-ranking" if dimension == "uf" else f"dimension-{dimension}"
            return {"key": spec_key, "type": chart_type, "title": title,
                    "subtitle": subtitle, "dimension": dimension, "metric": metric,
                    "unit": cls._chart_unit(metric), "labels": [item["label"] for item in entries],
                    "values": [item["value"] for item in entries], "details": entries,
                    "complementary": complementary}

        primary_is_fixed = bool(fixed.get(group) and filters.get(fixed[group]))
        if group != "month" and not primary_is_fixed and grouped:
            primary_spec = dimension_spec(group, grouped)
            if primary_spec:
                specs.append(primary_spec)

        if rows is not None and links is not None:
            complementary_count = 0
            for dimension in ("uf", "status", "priority", "source_state", "sla"):
                if dimension == group or filters.get(fixed.get(dimension, "")):
                    continue
                rows_by_dimension = cls._grouped(rows, metric, dimension, links, ())
                if len(rows_by_dimension) <= 1:
                    continue
                spec = dimension_spec(dimension, rows_by_dimension, complementary=True)
                if spec:
                    specs.append(spec)
                    complementary_count += 1
                if complementary_count == 2:
                    break
        return specs[:4]

    @staticmethod
    def _chart_unit(metric):
        if metric == "links_affected":
            return "links"
        if metric == "recurrences":
            return "links reincidentes"
        return "tickets"

    @classmethod
    def _monthly_calendar(cls, rows, metric, start, end, requested_month, overview, links):
        if metric in cls.SNAPSHOT_METRICS:
            return None

        month_keys = _months(start, end)
        month_buckets = [(key, cls._month_label(key), bucket_start, bucket_end)
                         for key, bucket_start, bucket_end in _month_buckets(start, end)]
        if overview and all(len(item["key"]) == 7 for item in overview):
            month_values = {item["key"]: item["value"] for item in overview}
        else:
            month_values = cls._aggregate_period_values(rows, metric, month_buckets, links)

        available = []
        for key in month_keys:
            year, month_number = map(int, key.split("-"))
            long_label = cls._month_label(key, long=True)
            available.append({
                "key": key, "label": f"{long_label.split(' de ')[0]}/{year}",
                "short_label": cls._month_label(key), "full_label": long_label,
                "value": month_values.get(key, 0),
            })
        latest_with_data = next((item for item in reversed(available) if item["value"] > 0), None)
        selected = next((item for item in available if item["key"] == requested_month), None)
        selected = selected or latest_with_data or (available[-1] if available else None)
        if not selected:
            return None

        year, month_number = map(int, selected["key"].split("-"))
        month_start = date(year, month_number, 1)
        month_end = cls._month_end(month_start)
        _grain, day_buckets = _time_buckets(month_start, month_end)
        day_values = cls._aggregate_period_values(rows, metric, day_buckets, links)
        calendar_rows = []
        in_range_values = []
        for week in calendar.Calendar(firstweekday=0).monthdatescalendar(year, month_number):
            row = []
            for day in week:
                inside_month = day.month == month_number
                inside_period = inside_month and start <= day <= end
                value = day_values.get(day.isoformat(), 0) if inside_period else 0
                if inside_period:
                    in_range_values.append((day, value))
                row.append({
                    "date": day.isoformat(), "day": day.day if inside_month else None,
                    "value": value if inside_month else None,
                    "inside_month": inside_month, "inside_query_period": inside_period,
                    "has_data": bool(inside_period and value),
                })
            calendar_rows.append(row)

        active_days = [(day, value) for day, value in in_range_values if value > 0]
        peak_day, peak_value = max(active_days, key=lambda item: (item[1], -item[0].day)) if active_days else (None, 0)
        month_total = month_values.get(selected["key"], 0)
        query_day_count = sum(1 for day, _value in in_range_values if start <= day <= end)
        daily_sum = sum(value for _day, value in in_range_values)
        unit = cls._chart_unit(metric)
        summary = {
            "total": month_total,
            "daily_total": daily_sum,
            "average_per_day": round(month_total / query_day_count, 1) if query_day_count else 0,
            "peak_day": peak_day.isoformat() if peak_day else None,
            "peak_value": peak_value,
            "days_with_occurrence": len(active_days),
            "days_in_query_period": query_day_count,
            "unit": unit,
        }
        flat_days = [day for week in calendar_rows for day in week]
        max_daily = max((item["value"] or 0 for item in flat_days if item["inside_query_period"]), default=0)
        for item in flat_days:
            value = item["value"] or 0
            item["share_of_month"] = round(value * 100 / daily_sum, 1) if item["inside_query_period"] and daily_sum else 0
            item["intensity"] = round(value / max_daily, 3) if item["inside_query_period"] and max_daily else 0
            item["accessible_label"] = (
                f"{item['day']} de {cls._month_label(selected['key'], long=True).split(' de ')[0]} de {year}, "
                f"{value} {unit}" if item["inside_month"] and item["inside_query_period"]
                else "Fora do período analisado" if item["inside_month"] else ""
            )

        calendar_spec = {
            "key": "monthly-calendar", "type": "monthly_calendar",
            "title": f"Detalhe de {selected['label']}", "month": selected["key"],
            "month_title": selected["full_label"], "unit": unit,
            "weekdays": ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"],
            "weeks": calendar_rows, "summary": summary,
        }
        return {
            "overview": overview, "available_months": available,
            "selected_month": selected["key"], "selected_month_label": selected["label"],
            "calendar_days": flat_days, "calendar_weeks": calendar_rows,
            "weekdays": calendar_spec["weekdays"], "month_summary": summary, "unit": unit, "chart_spec": calendar_spec,
        }

    @classmethod
    def _aggregate_period_values(cls, rows, metric, buckets, links):
        from django.db.models import Count

        if metric in cls.SNAPSHOT_METRICS or not buckets:
            return {}
        period_case = _period_case(cls._metric_date_field(metric), buckets)
        if metric == "recurrences":
            relation = OTRSTicketConfigItem.objects.filter(
                ticket_id__in=rows.values("pk"), is_present_in_source=True,
                cmdb_link__is_present_in_source=True, cmdb_link__in=links,
            ).annotate(period=period_case)
            grouped = relation.exclude(period__isnull=True).values("period", "cmdb_link_id").annotate(
                ticket_count=Count("ticket_id", distinct=True),
            ).filter(ticket_count__gte=2).values("period").annotate(
                value=Count("cmdb_link_id", distinct=True),
            )
        elif metric == "links_affected":
            relation = OTRSTicketConfigItem.objects.filter(
                ticket_id__in=rows.values("pk"), is_present_in_source=True,
                cmdb_link__is_present_in_source=True, cmdb_link__in=links,
            ).annotate(period=period_case)
            grouped = relation.exclude(period__isnull=True).values("period").annotate(
                value=Count("cmdb_link_id", distinct=True),
            )
        else:
            grouped = rows.annotate(period=period_case).exclude(period__isnull=True).values("period").annotate(
                value=Count("pk", distinct=True),
            )
        return {item["period"]: item["value"] for item in grouped}

    @classmethod
    def normalize_query(cls, payload):
        start_value, end_value = payload.get("start") or payload.get("date_from"), payload.get("end") or payload.get("date_to")
        try:
            if start_value or end_value:
                start = date.fromisoformat(start_value) if start_value else _month_date(payload.get("period_from"))
                end = date.fromisoformat(end_value) if end_value else cls._month_end(_month_date(payload.get("period_to")))
            else:
                start = _month_date(payload.get("period_from"))
                end = cls._month_end(_month_date(payload.get("period_to")))
        except (TypeError, ValueError):
            raise ValueError("Data ou per\u00edodo inv\u00e1lido.") from None
        if start > end:
            raise ValueError("A data inicial n\u00e3o pode ser posterior \u00e0 data final.")

        metric = payload.get("metric", "tickets")
        if metric == "links":
            metric = "tickets"
        raw_group = payload.get("group_by", "provider")
        group = cls.LEGACY_DIMENSIONS.get(raw_group, raw_group)
        if metric not in cls.METRICS or group not in cls.DIMENSIONS:
            raise ValueError("M\u00e9trica ou dimens\u00e3o n\u00e3o autorizada.")

        raw_filters = payload.get("filters", {})
        if not isinstance(raw_filters, dict):
            raise ValueError("Filtros inv\u00e1lidos.")
        raw_filters = dict(raw_filters)
        for alias, canonical in cls.FILTER_ALIASES.items():
            if alias in raw_filters and canonical not in raw_filters:
                raw_filters[canonical] = raw_filters[alias]
            raw_filters.pop(alias, None)
        unknown = set(raw_filters) - cls.FILTERS - set(cls.LEGACY_FILTERS)
        if unknown:
            raise ValueError("Filtro n\u00e3o autorizado.")
        filters = {}
        for key, value in raw_filters.items():
            canonical = cls.LEGACY_FILTERS.get(key, key)
            if not canonical or value in (None, "", "all"):
                continue
            if not isinstance(value, (str, int)):
                raise ValueError("Valor de filtro inv\u00e1lido.")
            normalized = str(value).strip()
            if not normalized or normalized.casefold() == "all":
                continue
            if canonical in {"uf", "status"}:
                normalized = normalized.upper()
            elif canonical == "termination_reason":
                normalized = normalize_closing_reason(normalized)
            filters[canonical] = normalized
        compare = payload.get("compare_to") or None
        if compare:
            _month_date(compare)
        selected_month = payload.get("selected_month") or None
        if selected_month:
            selected_month = _month_date(selected_month).strftime("%Y-%m")
        return {"metric": metric, "group_by": group, "start": start, "end": end,
                "filters": filters, "compare_to": compare, "selected_month": selected_month}

    @staticmethod
    def _month_end(month_start):
        next_month = date(month_start.year + (month_start.month == 12),
                          1 if month_start.month == 12 else month_start.month + 1, 1)
        return next_month - timedelta(days=1)

    @classmethod
    def _metric_semantics(cls, metric):
        if metric == "tickets":
            return "Data de cria\u00e7\u00e3o; inclui apenas estados operacionais v\u00e1lidos. CANCELED e UNKNOWN ficam de fora."
        if metric in {"open_tickets", "pending_tickets", "scheduled_tickets"}:
            status = cls.METRIC_STATUS[metric]
            return f"Data de cria\u00e7\u00e3o no per\u00edodo; tickets atualmente no estado {status}. CANCELED e UNKNOWN ficam de fora."
        if metric == "resolved_closed_tickets":
            return "Data terminal no per\u00edodo; estados RESOLVED e CLOSED, sem CANCELED."
        if metric in {"resolved_tickets", "closed_tickets"}:
            return "Data terminal no per\u00edodo; estado atual correspondente, sem CANCELED."
        if metric == "canceled_tickets":
            return "Data de cancelamento no per\u00edodo; estado CANCELED, em m\u00e9trica espec\u00edfica."
        if metric in cls.SNAPSHOT_METRICS:
            return "Snapshot atual da fila; datas n\u00e3o restringem o resultado."
        return "Data de cria\u00e7\u00e3o no per\u00edodo."

    @staticmethod
    def _comparison(filtered, query, links, current_value):
        metric = query["metric"]
        if metric in AnalyticsQueryService.SNAPSHOT_METRICS:
            return None
        if query["compare_to"]:
            previous_start = _month_date(query["compare_to"])
            previous_end = previous_start + (query["end"] - query["start"])
        else:
            previous_start, previous_end = AnalyticsQueryService._previous_period(query["start"], query["end"])
        previous_from, previous_to = _date_boundaries(previous_start, previous_end)
        date_field = AnalyticsQueryService._metric_date_field(metric)
        previous_rows = filtered.filter(**{f"{date_field}__gte": previous_from, f"{date_field}__lt": previous_to})
        previous_rows = AnalyticsQueryService._metric_rows(filtered, previous_rows, metric)
        previous_value = AnalyticsQueryService._metric_value(previous_rows, metric, links)
        _, previous_buckets = _time_buckets(previous_start, previous_end)
        previous_series = AnalyticsQueryService._series(previous_rows, metric, previous_buckets, links, previous_value)
        grouped = AnalyticsQueryService._grouped(previous_rows, metric, query["group_by"], links, previous_buckets)
        previous_grouped = []
        denominator = previous_value
        quality = None if metric in {"links_affected", "recurrences"} else AnalyticsQueryService._provider_quality(previous_rows, links)
        if quality and query["group_by"] == "provider" and metric not in {"links_affected", "recurrences"}:
            denominator = quality["identified"]
        for row in list(grouped[:10]):
            raw = row["dimension"] if row["dimension"] not in (None, "") else "N\\u00e3o classificado"
            label = AnalyticsQueryService._dimension_label(query["group_by"], raw)
            previous_grouped.append({"label": label, "value": row["value"],
                                     "share": round(row["value"] * 100 / denominator, 1) if denominator else 0})
        difference = current_value - previous_value
        return {"current_value": current_value, "previous_value": previous_value,
                "absolute_change": difference,
                "percentage_change": round(difference * 100 / previous_value, 1) if previous_value else (0 if difference == 0 else None),
                "value": previous_value, "difference": difference,
                "percent": round(difference * 100 / previous_value, 1) if previous_value else (0 if difference == 0 else None),
                "direction": "up" if difference > 0 else "down" if difference < 0 else "neutral",
                "previous_start": previous_start.isoformat(), "previous_end": previous_end.isoformat(),
                "provider_quality": quality, "previous_series": previous_series,
                "previous_grouped": previous_grouped}

    @classmethod
    def _apply_filters(cls, tickets, links, filters):
        from django.db.models import Q

        query = {}
        for key, field in (("status", "business_status"), ("source_state", "external_state_name"), ("service", "service_name"), ("sla", "sla_name")):
            if filters.get(key):
                query[field] = filters[key]
        filtered = tickets.filter(**query) if query else tickets
        priority = filters.get("priority")
        if priority == "high-critical":
            import unicodedata
            names = list(filtered.exclude(priority_name="").values_list("priority_name", flat=True).distinct())
            selected = [name for name in names if unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().casefold() in {"alto", "critico"}]
            filtered = filtered.filter(priority_name__in=selected)
        elif priority:
            filtered = filtered.filter(priority_name=priority)
        reason = filters.get("termination_reason")
        if reason:
            raw_values = [value for value in filtered.exclude(closing_code_raw="").values_list("closing_code_raw", flat=True).distinct()
                          if normalize_closing_reason(value) == reason]
            filtered = filtered.filter(closing_code_raw__in=raw_values)
        link_filters = {cls.LINK_FILTERS[key]: filters[key] for key in cls.LINK_FILTERS if filters.get(key)}
        if link_filters:
            filtered = filtered.filter(
                config_items__is_present_in_source=True,
                config_items__cmdb_link__is_present_in_source=True,
                config_items__cmdb_link__in=links,
                **link_filters,
            )
        return filtered.distinct()

    @staticmethod
    def _metric_date_field(metric):
        if metric == "canceled_tickets":
            return "canceled_at"
        if metric in {"resolved_tickets", "closed_tickets", "resolved_closed_tickets"}:
            return "terminal_state_at"
        return "source_created_at"

    @classmethod
    def _metric_rows(cls, filtered, historical, metric):
        if metric == "resolved_closed_tickets":
            return historical.filter(business_status__in=("RESOLVED", "CLOSED"))
        if metric in {"open_tickets", "pending_tickets", "scheduled_tickets"}:
            rows = historical
            if metric == "open_tickets":
                rows = rows.filter(business_status="OPEN")
            elif metric == "pending_tickets":
                rows = rows.filter(business_status="PENDING")
            return rows.filter(business_status="SCHEDULED") if metric == "scheduled_tickets" else rows
        if metric == "backlog":
            return filtered.filter(
                is_present_in_queue=True,
                business_status__in=("OPEN", "PENDING", "SCHEDULED"),
            )
        rows = historical
        if metric in cls.METRIC_STATUS:
            rows = rows.filter(business_status=cls.METRIC_STATUS[metric])
        return rows

    @classmethod
    def _metric_value(cls, rows, metric, links):
        from django.db.models import Count
        from aplicativos.integracoes.models import OTRSTicketConfigItem

        if metric == "recurrences":
            relation = OTRSTicketConfigItem.objects.filter(
                ticket_id__in=rows.values("pk"), is_present_in_source=True,
                cmdb_link__in=links,
            ).values("cmdb_link_id").annotate(ticket_count=Count("ticket_id", distinct=True)).filter(ticket_count__gte=2)
            return relation.count()
        if metric == "links_affected":
            return OTRSTicketConfigItem.objects.filter(
                ticket_id__in=rows.values("pk"), is_present_in_source=True,
                cmdb_link__in=links,
            ).values("cmdb_link_id").distinct().count()
        return rows.values("pk").distinct().count()

    @classmethod
    def _grouped(cls, rows, metric, group, links, buckets):
        from django.db.models import Count, F, Value
        from django.db.models.functions import Coalesce, NullIf
        from aplicativos.integracoes.models import OTRSTicketConfigItem

        if metric == "recurrences":
            relations = OTRSTicketConfigItem.objects.filter(
                ticket_id__in=rows.values("pk"), is_present_in_source=True,
                cmdb_link__is_present_in_source=True, cmdb_link__in=links,
            )
            if group == "month":
                period_case = _period_case("ticket__source_created_at", buckets)
                return relations.annotate(dimension=period_case).exclude(dimension__isnull=True).values(
                    "dimension", "cmdb_link_id",
                ).annotate(ticket_count=Count("ticket_id", distinct=True)).filter(
                    ticket_count__gte=2,
                ).values("dimension").annotate(value=Count("cmdb_link_id", distinct=True)).order_by("-value", "dimension")
            field = {
                "provider": "cmdb_link__operator__name",
                "uf": "cmdb_link__state",
                "status": "ticket__business_status",
                "source_state": "ticket__external_state_name",
                "service": "ticket__service_name",
                "sla": "ticket__sla_name",
                "priority": "ticket__priority_name",
                "termination_reason": "ticket__closing_code_raw",
            }[group]
            by_link = relations.annotate(dimension=Coalesce(NullIf(F(field), Value("")), Value("N\u00e3o classificado"))).values(
                "dimension", "cmdb_link_id",
            ).annotate(ticket_count=Count("ticket_id", distinct=True)).filter(ticket_count__gte=2)
            return by_link.values("dimension").annotate(value=Count("cmdb_link_id", distinct=True)).order_by("-value", "dimension")

        if group == "termination_reason":
            counts = rows.values("closing_code_raw").annotate(value=Count("pk", distinct=True))
            merged = {}
            for item in counts:
                label = normalize_closing_reason(item["closing_code_raw"])
                merged[label] = merged.get(label, 0) + item["value"]
            return [{"dimension": label, "value": value} for label, value in sorted(merged.items(), key=lambda item: (-item[1], item[0].casefold()))]

        amount = Count("config_items__cmdb_link_id", distinct=True) if metric == "links_affected" else Count("pk", distinct=True)
        if group == "month":
            if metric in cls.SNAPSHOT_METRICS:
                return [{"dimension": "Atual", "value": cls._metric_value(rows, metric, links)}]
            if metric == "links_affected":
                rows = rows.filter(config_items__is_present_in_source=True, config_items__cmdb_link__is_present_in_source=True, config_items__cmdb_link__in=links)
            period_case = _period_case(cls._metric_date_field(metric), buckets)
            return rows.annotate(dimension=period_case).exclude(dimension__isnull=True).values("dimension").annotate(value=amount).order_by("-value", "dimension")
        field = {
            "provider": "config_items__cmdb_link__operator__name",
            "uf": "config_items__cmdb_link__state",
            "status": "business_status",
            "source_state": "external_state_name",
            "service": "service_name",
            "sla": "sla_name",
            "priority": "priority_name",
            "termination_reason": "closing_code_raw",
        }[group]
        if group in cls.LINK_GROUPS:
            rows = rows.filter(config_items__is_present_in_source=True, config_items__cmdb_link__is_present_in_source=True, config_items__cmdb_link__in=links)
            if group == "provider":
                rows = rows.exclude(config_items__cmdb_link__operator__isnull=True).exclude(config_items__cmdb_link__operator__name="")
        rows = rows.annotate(dimension=Coalesce(NullIf(F(field), Value("")), Value("N\u00e3o classificado")))
        return list(rows.values("dimension").annotate(value=amount).order_by("-value", "dimension"))

    @classmethod
    def _series(cls, rows, metric, buckets, links, total_value):
        if metric in cls.SNAPSHOT_METRICS:
            return [{"key": "current", "label": "Atual", "long_label": "Situa\u00e7\u00e3o atual", "value": total_value}]
        values = cls._aggregate_period_values(rows, metric, buckets, links)
        details = []
        for key, label, bucket_start, bucket_end in buckets:
            if len(key) == 10 and key[4] == "-":
                long_label = date.fromisoformat(key).strftime("%d/%m/%Y")
            elif "-W" in key:
                local_start = bucket_start.astimezone(ZoneInfo(settings.TIME_ZONE)).date()
                local_end = (bucket_end - timedelta(microseconds=1)).astimezone(ZoneInfo(settings.TIME_ZONE)).date()
                long_label = f"Semana de {local_start:%d/%m/%Y} a {local_end:%d/%m/%Y}"
            else:
                long_label = cls._month_label(key, long=True)
            details.append({"key": key, "label": label, "long_label": long_label, "value": values.get(key, 0)})
        return details

    @staticmethod
    def _month_label(value, long=False):
        year, number = map(int, value.split("-"))
        names = ("Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez")
        full_names = ("Janeiro", "Fevereiro", "Mar\u00e7o", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro")
        return f"{full_names[number - 1]} de {year}" if long else f"{names[number - 1]}/{str(year)[-2:]}"

    @classmethod
    def _dimension_label(cls, group, value):
        if group == "status":
            return cls.STATUS_LABELS.get(value, "N\u00e3o classificado")
        if group == "source_state":
            return cls.SOURCE_STATE_LABELS.get(str(value).casefold(), value)
        if group == "month":
            if value == "Atual":
                return value
            return cls._month_label(value)
        return value

    @classmethod
    def _options(cls, tickets, links):
        result = {key: [] for key in cls.FILTERS}
        result["status"] = [
            {"value": value, "label": cls.STATUS_LABELS[value]}
            for value in tickets.values_list("business_status", flat=True).distinct().order_by("business_status")
            if value in cls.STATUS_LABELS
        ]
        result["source_state"] = [
            {"value": value, "label": cls.SOURCE_STATE_LABELS.get(value.casefold(), value)}
            for value in tickets.exclude(external_state_name="").values_list("external_state_name", flat=True).distinct().order_by("external_state_name")
        ]
        result["service"] = list(tickets.exclude(service_name="").values_list("service_name", flat=True).distinct().order_by("service_name"))
        result["priority"] = list(tickets.exclude(priority_name="").values_list("priority_name", flat=True).distinct().order_by("priority_name"))
        result["sla"] = list(tickets.exclude(sla_name="").values_list("sla_name", flat=True).distinct().order_by("sla_name"))
        reasons = {normalize_closing_reason(value) for value in tickets.exclude(closing_code_raw="").values_list("closing_code_raw", flat=True).distinct()}
        result["termination_reason"] = [{"value": value, "label": value} for value in sorted(reasons, key=str.casefold)]
        relation = OTRSTicketConfigItem.objects.filter(
            ticket_id__in=tickets.values("pk"), is_present_in_source=True,
            cmdb_link__in=links,
        )
        result["provider"] = list(relation.exclude(cmdb_link__operator__name="").exclude(cmdb_link__operator__isnull=True).values_list("cmdb_link__operator__name", flat=True).distinct().order_by("cmdb_link__operator__name"))
        result["uf"] = list(relation.exclude(cmdb_link__state="").values_list("cmdb_link__state", flat=True).distinct().order_by("cmdb_link__state"))
        return result

class DashboardAnalyticsService:
    """Build the executive Dashboard from scoped local CMDB and NOC mirrors."""

    @staticmethod
    def build(*, user, start, end):
        links = LinkQueryService.base(user)
        tickets = TicketQueryService.base(user, links=links)
        start_at, end_at = _date_boundaries(start, end)
        buckets = _month_buckets(start, end)
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

        provider_rows = list(
            links.filter(operator__isnull=False)
            .exclude(operator__name="")
            .values("operator__name")
            .annotate(value=Count("pk", distinct=True))
            .order_by("-value", "operator__name")[:10]
        )
        top_providers = [
            {"name": row["operator__name"], "value": row["value"]}
            for row in provider_rows
        ]

        snapshot_status = {row["business_status"]: row["total"] for row in current_tickets.values(
            "business_status"
        ).annotate(total=Count("pk"))}
        status_counts = {status: snapshot_status.get(status, 0) for status in STATUS_ORDER}
        open_count = status_counts[OTRSStateMapping.BusinessStatus.OPEN]
        pending_count = status_counts[OTRSStateMapping.BusinessStatus.PENDING]
        scheduled_count = status_counts[OTRSStateMapping.BusinessStatus.SCHEDULED]

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
            row["month"]: row["total"]
            for row in period_tickets.annotate(month=_month_case("source_created_at", buckets))
            .exclude(month__isnull=True).values("month").annotate(total=Count("pk"))
        }
        recurring_by_month = {}
        recurring_month_links = (
            recurrence_base.annotate(month=_month_case("ticket__source_created_at", buckets))
            .exclude(month__isnull=True)
            .values("month", "cmdb_link_id")
            .annotate(ticket_count=Count("ticket_id", distinct=True))
            .filter(ticket_count__gte=2)
        )
        for row in recurring_month_links:
            key = row["month"]
            recurring_by_month[key] = recurring_by_month.get(key, 0) + 1

        monthly = []
        for month_key, _month_start, _month_end in buckets:
            year, month = (int(part) for part in month_key.split("-"))
            month_label = AnalyticsQueryService._month_label(month_key).split("/")[0]
            monthly.append({
                "month": month_label,
                "label": f"{month_label}/{str(year)[-2:]}",
                "calls": calls_by_month.get(month_key, 0),
                "repeat": recurring_by_month.get(month_key, 0),
            })

        return {
            "total_links": total_links,
            "state_count": len(state_rows),
            "top_states": top_states,
            "top_providers": top_providers,
            "calls": calls,
            "repeat": recurrence_total,
            "business_open": business_open.count(),
            "open_count": open_count,
            "pending_count": pending_count,
            "scheduled_count": scheduled_count,
            "resolved_count": status_counts[OTRSStateMapping.BusinessStatus.RESOLVED],
            "closed_count": status_counts[OTRSStateMapping.BusinessStatus.CLOSED],
            "canceled_count": status_counts[OTRSStateMapping.BusinessStatus.CANCELED],
            "unknown_count": status_counts[OTRSStateMapping.BusinessStatus.UNKNOWN],
            "links_affected": links_affected,
            "monthly": monthly,
        }
