from collections import defaultdict
from datetime import date, datetime, time, timedelta
import unicodedata

from django.db.models import Prefetch, Q
from django.utils import timezone

from aplicativos.integracoes.models import OTRSTicketConfigItem, OTRSStateMapping
from aplicativos.integracoes.services.analytics import LinkQueryService, PeriodService, TicketQueryService
from aplicativos.integracoes.services.ticket_business_identity import TicketBusinessIdentityService
from aplicativos.integracoes.services.link_business_identity import BusinessIdentityRules
from aplicativos.integracoes.services.closing_reason import ClosingReasonCanonicalizer


STATE_NAMES = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapa", "AM": "Amazonas", "BA": "Bahia",
    "CE": "Ceara", "DF": "Distrito Federal", "ES": "Espirito Santo", "GO": "Goias",
    "MA": "Maranhao", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais",
    "PA": "Para", "PB": "Paraiba", "PR": "Parana", "PE": "Pernambuco", "PI": "Piaui",
    "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RS": "Rio Grande do Sul",
    "RO": "Rondonia", "RR": "Roraima", "SC": "Santa Catarina", "SP": "Sao Paulo",
    "SE": "Sergipe", "TO": "Tocantins",
}
STATE_NAMES_ACCENTED = {
    "AP": "Amap\u00e1", "CE": "Cear\u00e1", "ES": "Esp\u00edrito Santo", "GO": "Goi\u00e1s",
    "MA": "Maranh\u00e3o", "PA": "Par\u00e1", "PB": "Para\u00edba", "PI": "Piau\u00ed",
    "PR": "Paran\u00e1", "RO": "Rond\u00f4nia", "SP": "S\u00e3o Paulo",
}
CLIENT_KEYS = {"claro": "Claro", "vivo": "Vivo", "algar": "Algar"}
VALID_TICKET_STATES = (
    OTRSStateMapping.BusinessStatus.OPEN, OTRSStateMapping.BusinessStatus.PENDING,
    OTRSStateMapping.BusinessStatus.SCHEDULED, OTRSStateMapping.BusinessStatus.RESOLVED,
    OTRSStateMapping.BusinessStatus.CLOSED,
)
ACTIVE_TICKET_STATES = (
    OTRSStateMapping.BusinessStatus.OPEN, OTRSStateMapping.BusinessStatus.PENDING,
    OTRSStateMapping.BusinessStatus.SCHEDULED,
)


def _norm(value):
    text = unicodedata.normalize("NFKD", (value or "").strip())
    return " ".join("".join(char for char in text if not unicodedata.combining(char)).casefold().split())


def _uf(value):
    key = _norm(value)
    aliases = {code.casefold(): code for code in STATE_NAMES}
    aliases.update({_norm(name): code for code, name in STATE_NAMES.items()})
    return aliases.get(key, "")


def _bounds(params):
    period = (params.get("period") or "").strip()
    today = timezone.localdate()
    if period == "this_month":
        return today.replace(day=1), today
    if period == "last_month":
        end = today.replace(day=1) - timedelta(days=1)
        return end.replace(day=1), end
    if period == "last_30":
        return today - timedelta(days=29), today
    if period == "last_90":
        return today - timedelta(days=89), today
    if len(period) == 7 and period[4] == "-":
        try:
            year, month = (int(part) for part in period.split("-"))
            start = date(year, month, 1)
            next_month = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
            return start, next_month - timedelta(days=1)
        except (ValueError, TypeError):
            raise ValueError("Periodo do mapa invalido.") from None
    if period in {"", "custom"}:
        return PeriodService.parse(params)
    raise ValueError("Periodo do mapa invalido.")


def _datetime_bounds(start, end):
    current_tz = timezone.get_current_timezone()
    lower = timezone.make_aware(datetime.combine(start, time.min), current_tz) if start else None
    upper = timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min), current_tz) if end else None
    return lower, upper


def _client_filter(queryset, value):
    if not value or value == "all":
        return queryset
    if value == "other":
        return queryset.exclude(contracting_client="").exclude(contracting_client__in=(*CLIENT_KEYS.values(), "TELMEX"))
    if value == "Claro":
        return queryset.filter(Q(contracting_client="Claro") | Q(contracting_client="TELMEX"))
    return queryset.filter(contracting_client=value)


def _client_label_matches(label, requested):
    if not requested or requested == "all":
        return True
    if requested == "other":
        return bool(label) and label not in CLIENT_KEYS.values()
    return label == requested


class MapAnalyticsService:
    MODES = {"base", "projects", "calls", "repeat", "motives"}

    @classmethod
    def query(cls, user, params):
        mode = (params.get("mode") or "base").strip()
        if mode not in cls.MODES:
            raise ValueError("Modo de mapa invalido.")
        start, end = _bounds(params)
        client = (params.get("client") or "all").strip()
        project = (params.get("project") or "").strip()
        provider = (params.get("provider") or "").strip()
        reason_filter = ClosingReasonCanonicalizer.key(params.get("reason")) if params.get("reason") else ""
        status_filter = (params.get("status") or "").strip().upper()
        priority_filter = (params.get("priority") or "").strip()
        if status_filter not in {"", *VALID_TICKET_STATES}:
            raise ValueError("Status do ticket invalido.")
        if len(priority_filter) > 160:
            raise ValueError("Prioridade do ticket invalida.")
        uf_filter = (params.get("uf") or "").strip().upper()

        # Data Scope is applied first, before option catalogs, dimensions, and counts.
        scoped = LinkQueryService.base(user)
        filtered = _client_filter(scoped, client)
        ticket_candidates = scoped
        if project:
            filtered = filtered.filter(business_project=project)
        if provider:
            if not provider.isdigit():
                raise ValueError("Provedor do mapa invalido.")
            filtered = filtered.filter(operator__pk=int(provider), operator__is_present_in_source=True)
            ticket_candidates = ticket_candidates.filter(operator__pk=int(provider), operator__is_present_in_source=True)
        if uf_filter in STATE_NAMES:
            state_values = {uf_filter, STATE_NAMES[uf_filter], STATE_NAMES_ACCENTED.get(uf_filter, STATE_NAMES[uf_filter])}
            from django.db.models import Q
            state_q = Q()
            for value in state_values:
                state_q |= Q(state__iexact=value)
            filtered = filtered.filter(state_q)
            ticket_candidates = ticket_candidates.filter(state_q)
        source_total = scoped.count()
        filtered_total = filtered.count()

        project_scope = _client_filter(scoped, client)
        if provider:
            project_scope = project_scope.filter(operator__pk=int(provider), operator__is_present_in_source=True)
        clients = list(scoped.exclude(contracting_client="").exclude(contracting_client="TELMEX").values_list(
            "contracting_client", flat=True).distinct().order_by("contracting_client"))
        project_options = list(project_scope.exclude(business_project="").values_list(
            "business_project", flat=True).distinct().order_by("business_project"))
        providers = list(project_scope.filter(operator__is_present_in_source=True).values(
            "operator_id", "operator__name").distinct().order_by("operator__name"))

        start, end = (None, None) if mode in {"base", "projects"} else (start, end)
        start_at, end_exclusive = _datetime_bounds(start, end)
        current_relations = OTRSTicketConfigItem.objects.none()
        period_relations = OTRSTicketConfigItem.objects.none()
        terminal_relations = OTRSTicketConfigItem.objects.none()
        priority_options = []
        if mode in {"calls", "repeat", "motives"}:
            period_relations = OTRSTicketConfigItem.objects.filter(
                is_present_in_source=True, ticket__in=TicketQueryService.noc_tickets(),
                ticket__business_status__in=VALID_TICKET_STATES,
            ).select_related("ticket")
            current_relations = OTRSTicketConfigItem.objects.filter(
                is_present_in_source=True, ticket__in=TicketQueryService.noc_tickets(),
                ticket__business_status__in=ACTIVE_TICKET_STATES,
            ).select_related("ticket")
            terminal_relations = OTRSTicketConfigItem.objects.filter(
                is_present_in_source=True, ticket__in=TicketQueryService.noc_tickets(),
                ticket__business_status__in=(OTRSStateMapping.BusinessStatus.RESOLVED, OTRSStateMapping.BusinessStatus.CLOSED),
            ).exclude(ticket__closing_code_raw="").exclude(ticket__terminal_state_at__isnull=True).select_related("ticket")
            if start:
                period_relations = period_relations.filter(ticket__source_created_at__gte=start_at)
                terminal_relations = terminal_relations.filter(ticket__terminal_state_at__gte=start_at)
            if end:
                period_relations = period_relations.filter(ticket__source_created_at__lt=end_exclusive)
                terminal_relations = terminal_relations.filter(ticket__terminal_state_at__lt=end_exclusive)
            priority_options = list(period_relations.filter(cmdb_link__in=scoped).exclude(
                ticket__priority_name="").values_list("ticket__priority_name", flat=True).distinct().order_by("ticket__priority_name"))
            if mode == "calls" and status_filter:
                period_relations = period_relations.filter(ticket__business_status=status_filter)
            if mode == "calls" and priority_filter:
                period_relations = period_relations.filter(ticket__priority_name=priority_filter)
            if mode == "motives" and reason_filter:
                terminal_relations = terminal_relations.filter(
                    ticket__closing_code_raw__in=ClosingReasonCanonicalizer.raw_values(reason_filter),
                )
            query_links = ticket_candidates.prefetch_related(
                Prefetch("ticket_relations", queryset=period_relations, to_attr="_map_period"),
                Prefetch("ticket_relations", queryset=current_relations, to_attr="_map_active"),
                Prefetch("ticket_relations", queryset=terminal_relations, to_attr="_map_terminal"),
            )
        else:
            query_links = filtered

        result = {}
        global_tickets, global_ticket_statuses, global_ticket_priorities, global_ticket_reasons, active_ids, global_terminal = set(), {}, {}, {}, set(), set()
        global_ticket_contexts = {}
        ticket_identity_cache = {}
        def identity_for(ticket):
            if ticket.pk not in ticket_identity_cache:
                ticket_identity_cache[ticket.pk] = TicketBusinessIdentityService.parse(ticket.title)
            return ticket_identity_cache[ticket.pk]
        global_client_identified = global_client_unidentified = 0
        invalid_uf_count = 0
        for link in query_links.iterator(chunk_size=500):
            client_label = BusinessIdentityRules.client_for_token(link.contracting_client) or link.contracting_client
            link_matches = _client_label_matches(client_label, client) and (not project or link.business_project == project)
            if link_matches:
                if client_label:
                    global_client_identified += 1
                else:
                    global_client_unidentified += 1
            uf = _uf(link.state)
            if not uf:
                invalid_uf_count += int(link_matches)
                continue
            item = result.setdefault(uf, {
                "total_links": 0, "client_counts": {}, "project_counts": {}, "account_counts": {},
                "provider_counts": {}, "city_counts": {}, "ticket_status_counts": {},
                "ticket_client_counts": {}, "ticket_project_counts": {}, "ticket_provider_counts": {}, "ticket_priority_counts": {}, "ticket_reason_counts": {},
                "ticket_city_counts": {},
                "recurrence_client_counts": {}, "recurrence_provider_counts": {},
                "ticket_count": 0, "active_tickets": 0,
                "affected_links": 0, "recurrence_links": 0, "recurrence_tickets": 0,
                "terminal_links": 0, "reason_counts": {},
                "tickets_by_id": {}, "ticket_context_by_id": {}, "active_ticket_ids": set(), "terminal_by_id": {},
            })
            if link_matches:
                item["total_links"] += 1
                _inc(item["client_counts"], client_label or "Cliente não identificado")
                _inc(item["project_counts"], link.business_project or "Projeto não identificado")
                _inc(item["account_counts"], link.business_account or "Conta não identificada")
                _inc(item["provider_counts"], link.operator.name if link.operator_id and link.operator.is_present_in_source else "Provedor não identificado")
                if link.city:
                    city_key = _norm(link.city)
                    city = item["city_counts"].setdefault(city_key, {"count": 0, "variants": {}})
                    city["count"] += 1
                    city["variants"][link.city.strip()] = city["variants"].get(link.city.strip(), 0) + 1
            period_rows = getattr(link, "_map_period", [])
            active_rows = getattr(link, "_map_active", [])
            terminal_rows = getattr(link, "_map_terminal", [])
            def context_matches(ticket):
                parsed = identity_for(ticket)
                ticket_client = parsed.client or client_label
                ticket_project = parsed.project or link.business_project
                return _client_label_matches(ticket_client, client) and (not project or ticket_project == project)
            tickets = {rel.ticket_id: rel.ticket for rel in period_rows if context_matches(rel.ticket)}
            active = {rel.ticket_id for rel in active_rows if context_matches(rel.ticket)}
            terminal = {rel.ticket_id: rel.ticket for rel in terminal_rows if context_matches(rel.ticket)}
            global_tickets.update(tickets)
            global_ticket_statuses.update({ticket_id: ticket.business_status for ticket_id, ticket in tickets.items()})
            global_ticket_priorities.update({ticket_id: ticket.priority_name for ticket_id, ticket in tickets.items()})
            global_ticket_reasons.update({ticket_id: ClosingReasonCanonicalizer.display(ticket.closing_code_raw) for ticket_id, ticket in tickets.items()})
            active_ids.update(active)
            global_terminal.update(terminal)
            item["tickets_by_id"].update(tickets)
            context_tickets = terminal if mode == "motives" else tickets
            for ticket_id, ticket in context_tickets.items():
                identity = identity_for(ticket)
                linked_client = client_label
                linked_project = link.business_project
                context = {
                    "client": identity.client or linked_client or "Cliente n\u00e3o identificado",
                    "project": identity.project or linked_project or "Projeto n\u00e3o identificado",
                    "provider": link.operator.name if link.operator_id and link.operator.is_present_in_source else "Provedor n\u00e3o identificado",
                }
                item["ticket_context_by_id"].setdefault(ticket_id, context)
                global_ticket_contexts.setdefault(ticket_id, context)
            if link.city and context_tickets and (mode != "repeat" or len(tickets) >= 2):
                _inc(item["ticket_city_counts"], link.city.strip())
            item["active_ticket_ids"].update(active)
            item["terminal_by_id"].update(terminal)
            if tickets:
                item["affected_links"] += 1
            if len(tickets) >= 2:
                item["recurrence_links"] += 1
                item["recurrence_tickets"] += len(tickets)
                _inc(item["recurrence_client_counts"], client_label or "Cliente não identificado")
                _inc(item["recurrence_provider_counts"], link.operator.name if link.operator_id and link.operator.is_present_in_source else "Provedor não identificado")
            if terminal:
                item["terminal_links"] += 1
        result = {uf: item for uf, item in result.items() if item["total_links"] or item["tickets_by_id"]}
        for item in result.values():
            total_links = item["total_links"]
            identified = total_links - item["client_counts"].get("Cliente não identificado", 0)
            item["client_identified_links"] = identified
            item["client_unidentified_links"] = total_links - identified
            item["client_coverage"] = round(identified / total_links * 100, 1) if total_links else 0
            city_counts = {}
            for city in item["city_counts"].values():
                variants = city["variants"]
                accented = [label for label in variants if any(unicodedata.combining(char) for char in unicodedata.normalize("NFD", label))]
                candidates = accented or list(variants)
                label = max(candidates, key=lambda value: (variants[value], value != value.upper(), len(value)))
                if not accented or label.isupper():
                    label = label.title()
                city_counts[label] = city_counts.get(label, 0) + city["count"]
            item["city_counts"] = city_counts
            item["ticket_count"] = len(item["tickets_by_id"])
            item["active_tickets"] = len(item["active_ticket_ids"])
            for ticket in item["tickets_by_id"].values():
                _inc(item["ticket_status_counts"], ticket.business_status)
                if ticket.priority_name:
                    _inc(item["ticket_priority_counts"], ticket.priority_name)
                reason = ClosingReasonCanonicalizer.display(ticket.closing_code_raw)
                if reason:
                    _inc(item["ticket_reason_counts"], reason)
            for context in item["ticket_context_by_id"].values():
                _inc(item["ticket_client_counts"], context["client"])
                _inc(item["ticket_project_counts"], context["project"])
                _inc(item["ticket_provider_counts"], context["provider"])
            for ticket in item["terminal_by_id"].values():
                reason = ClosingReasonCanonicalizer.display(ticket.closing_code_raw)
                if reason:
                    _inc(item["reason_counts"], reason)
            item.pop("tickets_by_id")
            item.pop("ticket_context_by_id")
            item.pop("active_ticket_ids")
            item.pop("terminal_by_id")

        reasons = sorted({reason for row in result.values() for reason in row["reason_counts"]})
        reason_options = set(reasons)
        if reason_filter:
            reason_options.add(ClosingReasonCanonicalizer.display(reason_filter))
        status_counts, priority_counts, ticket_reason_counts = {}, {}, {}
        for status in global_ticket_statuses.values():
            _inc(status_counts, status)
        for priority in global_ticket_priorities.values():
            if priority:
                _inc(priority_counts, priority)
        for reason in global_ticket_reasons.values():
            if reason:
                _inc(ticket_reason_counts, reason)
        recurrence_clients, recurrence_providers = {}, {}
        ticket_clients, ticket_projects, ticket_providers = {}, {}, {}
        for row in result.values():
            for label, amount in row["recurrence_client_counts"].items():
                _inc(recurrence_clients, label, amount)
            for label, amount in row["recurrence_provider_counts"].items():
                _inc(recurrence_providers, label, amount)
        selected_context_ids = global_terminal if mode == "motives" else global_tickets
        for ticket_id in selected_context_ids:
            context = global_ticket_contexts.get(ticket_id)
            if not context:
                continue
            _inc(ticket_clients, context["client"])
            _inc(ticket_projects, context["project"])
            _inc(ticket_providers, context["provider"])
        metric_fields = {"base": "total_links", "projects": "total_links", "calls": "ticket_count",
                         "repeat": "recurrence_links", "motives": "motives"}
        metric = metric_fields[mode]
        return {
            "mode": mode, "location_mode": "uf", "states": result,
            "source_total": source_total, "filtered_source_total": filtered_total,
            "client_identified_count": global_client_identified,
            "client_unidentified_count": global_client_unidentified,
            "client_coverage": round(global_client_identified / filtered_total * 100, 1) if filtered_total else 0,
            "valid_uf_count": filtered_total - invalid_uf_count, "invalid_uf_count": invalid_uf_count,
            "ticket_count": len(global_tickets), "active_ticket_count": len(active_ids),
            "affected_link_count": sum(row["affected_links"] for row in result.values()),
            "recurrence_link_count": sum(row["recurrence_links"] for row in result.values()),
            "recurrence_ticket_count": sum(row["recurrence_tickets"] for row in result.values()),
            "terminal_ticket_count": len(global_terminal), "metric": metric,
            "terminal_link_count": sum(row["terminal_links"] for row in result.values()),
            "ticket_status_counts": status_counts,
            "ticket_priority_counts": priority_counts, "priority_options": priority_options,
            "ticket_reason_counts": ticket_reason_counts,
            "ticket_client_counts": ticket_clients,
            "ticket_project_counts": ticket_projects,
            "ticket_provider_counts": ticket_providers,
            "recurrence_client_counts": recurrence_clients,
            "recurrence_provider_counts": recurrence_providers,
            "clients": clients, "projects": project_options,
            "providers": [{"id": row["operator_id"], "name": row["operator__name"]} for row in providers],
            "reasons": reasons, "reason_options": [
                {**option, "raw_values": list(ClosingReasonCanonicalizer.raw_values(option["value"]))}
                for option in ClosingReasonCanonicalizer.options(reason_options)
            ],
            "period": {"date_from": start.isoformat() if start else "", "date_to": end.isoformat() if end else ""},
        }


def _inc(counter, key, amount=1):
    counter[key] = counter.get(key, 0) + amount
