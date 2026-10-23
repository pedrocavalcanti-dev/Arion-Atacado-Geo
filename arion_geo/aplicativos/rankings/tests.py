from datetime import datetime, timezone as datetime_timezone

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from aplicativos.configuracoes.models import GroupDataScope
from aplicativos.base_links.models import Operadora
from aplicativos.integracoes.models import CMDBLinkMirror, CMDBOperatorMirror, OTRSTicket, OTRSTicketConfigItem


class RankingsMirrorTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="rank-mirror", password="safe-password-1")
        group = Group.objects.get(name="Analista NOC")
        self.user.groups.set([group])
        scope, _ = GroupDataScope.objects.get_or_create(group=group)
        scope.mode = GroupDataScope.Mode.ALL
        scope.save()
        self.operator = CMDBOperatorMirror.objects.create(source_config_item_id="op-1", name="Operadora Real")
        self.link = CMDBLinkMirror.objects.create(source_config_item_id="ci-1", source_number="N-1", name="Link Real", state="SP", operator=self.operator)
        self.client.force_login(self.user)

    def test_rankings_use_real_mirror_and_have_no_demo_labels(self):
        response = self.client.get(reverse("rankings:index"), {"date_from": "2026-10-01", "date_to": "2026-10-31"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Operadora Real")
        self.assertNotContains(response, "DEMONSTRA")
        self.assertEqual(response.context["total_links"], 1)

    def test_link_counts_and_ticket_metrics_are_distinct_and_recurrent(self):
        first = OTRSTicket.objects.create(external_id=1, ticket_number="T-1", queue_external_id=107, queue_name="NOC - ATACADO", external_state_id=1, external_state_name="em atendimento", business_status="OPEN", is_business_open=True, source_created_at=datetime(2026, 10, 5, tzinfo=datetime_timezone.utc))
        second = OTRSTicket.objects.create(external_id=2, ticket_number="T-2", queue_external_id=107, queue_name="NOC - ATACADO", external_state_id=2, external_state_name="resolvido", business_status="RESOLVED", is_business_open=False, source_created_at=datetime(2026, 10, 6, tzinfo=datetime_timezone.utc))
        for ticket in (first, second):
            OTRSTicketConfigItem.objects.create(ticket=ticket, config_item_id="ci-1", cmdb_link=self.link, relation_type="DependsOn", relation_state="Valid")
        # One ticket associated to a second CI must still count once in the global KPI.
        other = CMDBLinkMirror.objects.create(source_config_item_id="ci-2", source_number="N-2", operator=self.operator)
        OTRSTicketConfigItem.objects.create(ticket=first, config_item_id="ci-2", cmdb_link=other, relation_type="DependsOn", relation_state="Valid")
        response = self.client.get(reverse("rankings:index"), {"date_from": "2026-10-01", "date_to": "2026-10-31"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_tickets"], 2)
        self.assertEqual(response.context["open_tickets"], 1)
        self.assertEqual(response.context["operators"][0]["tickets"], 2)
        self.assertEqual(response.context["operators"][0]["recurrence_links"], 1)
        self.assertEqual(response.context["ranked_links"][0]["tickets"], 2)

    def test_custom_scope_excludes_links_without_allowed_project(self):
        outside = CMDBLinkMirror.objects.create(source_config_item_id="ci-out", operator=self.operator, legacy_project="Outside")
        group = self.user.groups.get(name="Analista NOC")
        scope = group.data_scope
        scope.mode = GroupDataScope.Mode.CUSTOM
        scope.save()
        scope.allowed_operators.set([Operadora.objects.create(name=self.operator.name, normalized_name=self.operator.name.casefold())])
        # CUSTOM project selection is restrictive; empty-project links are not implicitly allowed.
        response = self.client.get(reverse("rankings:index"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_links"], 0)
