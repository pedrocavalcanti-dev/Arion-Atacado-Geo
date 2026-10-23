from collections import defaultdict

from aplicativos.integracoes.models import OTRSTicketConfigItem
from aplicativos.integracoes.services.analytics import LinkQueryService, TicketQueryService
from aplicativos.integracoes.services.semantics import provider_label


class RankingService:
    """Transparent operator and link rankings from scoped mirror snapshots."""
    @staticmethod
    def build(user, *, date_from=None, date_to=None, operator_id="", project="", query=""):
        links_qs = LinkQueryService.base(user)
        if operator_id:
            links_qs = links_qs.filter(operator_id=operator_id)
        if project:
            links_qs = links_qs.filter(legacy_project=project)
        if query:
            from django.db.models import Q
            links_qs = links_qs.filter(Q(operator__name__icontains=query) | Q(isp_raw__icontains=query) | Q(name__icontains=query) | Q(source_number__icontains=query))
        links = list(links_qs.select_related("operator"))
        by_id = {link.pk: link for link in links}
        operator_tickets = defaultdict(set)
        operator_open = defaultdict(set)
        operator_links_open = defaultdict(set)
        per_link_tickets = defaultdict(set)
        period_ticket_ids = set()
        period_open_ticket_ids = set()
        per_link_open = defaultdict(set)
        relations = OTRSTicketConfigItem.objects.filter(
            is_present_in_source=True,
            ticket__queue_name=TicketQueryService.QUEUE_NAME,
            ticket__is_present_in_queue=True,
            cmdb_link_id__in=links_qs.values("pk"),
        ).select_related("ticket", "cmdb_link__operator")
        for relation in relations:
            ticket = relation.ticket
            link = relation.cmdb_link
            created = ticket.source_created_at.date() if ticket.source_created_at else None
            in_period = not (date_from and (created is None or created < date_from)) and not (date_to and (created is None or created > date_to))
            if ticket.is_business_open:
                if link.operator_id:
                    operator_open[link.operator_id].add(ticket.pk)
                    operator_links_open[link.operator_id].add(link.pk)
                per_link_open[link.pk].add(ticket.pk)
            if not in_period:
                continue
            period_ticket_ids.add(ticket.pk)
            if ticket.is_business_open: period_open_ticket_ids.add(ticket.pk)
            per_link_tickets[link.pk].add(ticket.pk)
            if link.operator_id:
                operator_tickets[link.operator_id].add(ticket.pk)
        recurrence_by_operator = defaultdict(int)
        for link in links:
            if link.operator_id and len(per_link_tickets[link.pk]) >= 2:
                recurrence_by_operator[link.operator_id] += 1
        operators = {}
        for link in links:
            if not link.operator_id:
                continue
            item = operators.setdefault(link.operator_id, {"id": link.operator_id, "name": link.operator.name, "links": 0, "tickets": 0, "open_tickets": 0, "affected_links": 0, "recurrence_links": 0, "projects": set(), "states": set(), "isps": set(), "tickets_per_link": 0, "affected_ratio": 0})
            item["links"] += 1
            if link.legacy_project: item["projects"].add(link.legacy_project)
            if link.state: item["states"].add(link.state)
            if link.operator_id:
                item["isps"].add(provider_label(link))
        total_links = len(links)
        for operator_id, item in operators.items():
            item["tickets"] = len(operator_tickets[operator_id])
            item["open_tickets"] = len(operator_open[operator_id])
            item["affected_links"] = len(operator_links_open[operator_id])
            item["recurrence_links"] = recurrence_by_operator[operator_id]
            item["tickets_per_link"] = round(item["tickets"] / item["links"], 3) if item["links"] else 0
            item["affected_ratio"] = round(item["affected_links"] / item["links"] * 100, 1) if item["links"] else 0
            item["share"] = round(item["links"] / total_links * 100, 1) if total_links else 0
            item["projects"] = sorted(item["projects"])
            item["states"] = sorted(item["states"])
            item["isps"] = sorted(item["isps"])
            item["logo"] = "".join(part[0] for part in item["name"].split()[:2]).upper()
        ranked_links = []
        for link in links:
            ids = per_link_tickets[link.pk]
            if not ids: continue
            ranked_links.append({"id": link.pk, "name": link.designation or link.name or link.source_number or link.source_config_item_id,
                "config_item_id": link.source_config_item_id, "number": link.source_number or "", "operator": provider_label(link),
                "project": link.legacy_project, "state": link.state, "isp": provider_label(link), "isp_raw": link.isp_raw, "tickets": len(ids),
                "open_tickets": len(per_link_open[link.pk]), "is_recurrent": len(ids) >= 2})
        ranked_links.sort(key=lambda row: (-row["tickets"], -row["open_tickets"], row["name"].casefold()))
        return sorted(operators.values(), key=lambda row: (-row["tickets"], row["name"].casefold())), ranked_links, total_links, {"tickets": len(period_ticket_ids), "open_tickets": len(period_open_ticket_ids)}
