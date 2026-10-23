"""Shared local-only querysets for operational analytics consumers."""
from datetime import date

from django.db.models import Count, Exists, OuterRef, Q

from aplicativos.configuracoes.data_scope import DataScopeService
from aplicativos.integracoes.models import CMDBLinkMirror, OTRSTicket, OTRSTicketConfigItem


class LinkQueryService:
    @staticmethod
    def base(user=None):
        links = CMDBLinkMirror.objects.filter(is_present_in_source=True).select_related("operator")
        return DataScopeService.filter_queryset(user, links) if user is not None else links


class TicketQueryService:
    QUEUE_NAME = "NOC - ATACADO"

    @classmethod
    def noc_tickets(cls):
        """Current operational ticket universe, resolved by the configured queue name."""
        return OTRSTicket.objects.filter(queue_name=cls.QUEUE_NAME, is_present_in_queue=True)

    @staticmethod
    def base(user=None, *, links=None):
        tickets = TicketQueryService.noc_tickets()
        if user is None or DataScopeService.is_global(user):
            return tickets
        allowed = links if links is not None else LinkQueryService.base(user)
        related = OTRSTicketConfigItem.objects.filter(
            ticket_id=OuterRef("pk"), is_present_in_source=True, cmdb_link__in=allowed,
        )
        return tickets.annotate(_has_allowed_link=Exists(related)).filter(_has_allowed_link=True)


class PeriodService:
    """Interpret explicit creation-date bounds without implying historical state snapshots."""
    @staticmethod
    def parse(params):
        def bound(name):
            value = (params.get(name) or "").strip()
            if not value:
                return None
            try:
                return date.fromisoformat(value)
            except ValueError:
                raise ValueError(f"Data inválida: {name}.") from None
        start, end = bound("date_from"), bound("date_to")
        if start and end and start > end:
            raise ValueError("A data inicial deve ser anterior à data final.")
        return start, end

    @staticmethod
    def parse_month(value):
        try:
            return date.fromisoformat(f"{value}-01")
        except (TypeError, ValueError):
            raise ValueError("Período mensal inválido.") from None

    @staticmethod
    def tickets(queryset, start=None, end=None):
        if start:
            queryset = queryset.filter(source_created_at__date__gte=start)
        if end:
            queryset = queryset.filter(source_created_at__date__lte=end)
        return queryset


def ticket_counts_by_link(user=None):
    links = LinkQueryService.base(user)
    relation = OTRSTicketConfigItem.objects.filter(
        cmdb_link_id=OuterRef("pk"), is_present_in_source=True,
        ticket__queue_name=TicketQueryService.QUEUE_NAME,
        ticket__is_present_in_queue=True, ticket__is_business_open=True,
    )
    return links.annotate(has_open_ticket=Exists(relation)).annotate(
        open_ticket_count=Count("ticket_relations__ticket_id", filter=Q(
            ticket_relations__is_present_in_source=True,
            ticket_relations__ticket__queue_name=TicketQueryService.QUEUE_NAME,
            ticket_relations__ticket__is_present_in_queue=True,
            ticket_relations__ticket__is_business_open=True,
        ), distinct=True),
    )
