from datetime import datetime, timezone as datetime_timezone

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse
from aplicativos.configuracoes.models import GroupDataScope
from aplicativos.base_links.models import Operadora
from aplicativos.integracoes.models import CMDBLinkMirror, CMDBOperatorMirror, OTRSTicket, OTRSTicketConfigItem


class MapMirrorTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="map-user", password="safe-password-1")
        group = Group.objects.get(name="Analista NOC")
        self.user.groups.set([group])
        scope, _ = GroupDataScope.objects.get_or_create(group=group)
        scope.mode = GroupDataScope.Mode.ALL
        scope.save()
        self.operator = CMDBOperatorMirror.objects.create(source_config_item_id="map-op", name="Operadora Map")
        self.link = CMDBLinkMirror.objects.create(source_config_item_id="map-ci", source_number="MAP-1", state="SP", operator=self.operator, legacy_project="Projeto A")
        self.client.force_login(self.user)

    @override_settings(MAPBOX_PUBLIC_TOKEN="")
    def test_map_uses_local_mirror_and_no_demo_files(self):
        response = self.client.get(reverse("mapa:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-token=""')
        self.assertContains(response, "Espelho CMDB")
        self.assertNotContains(response, "data/demo/")
        self.assertContains(response, "data-cmdb-date-from")

    @override_settings(MAPBOX_PUBLIC_TOKEN="pk.test-token")
    def test_public_map_token_is_rendered(self):
        response = self.client.get(reverse("mapa:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-token="pk.test-token"')

    def test_map_aggregates_use_period_and_open_ticket_relationships(self):
        ticket = OTRSTicket.objects.create(external_id=20, ticket_number="M-20", queue_external_id=107, queue_name="NOC - ATACADO", external_state_id=1, external_state_name="em atendimento", business_status="OPEN", is_business_open=True, source_created_at=datetime(2026, 10, 5, tzinfo=datetime_timezone.utc))
        OTRSTicketConfigItem.objects.create(ticket=ticket, config_item_id="map-ci", cmdb_link=self.link, relation_type="DependsOn", relation_state="Valid")
        response = self.client.get(reverse("base_links:map-aggregates"), {"date_from": "2026-10-01", "date_to": "2026-10-31"})
        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["source_total"], 1)
        self.assertEqual(data["states"]["SP"]["total_links"], 1)
        self.assertEqual(data["states"]["SP"]["open_tickets"], 1)
        self.assertEqual(data["affected_link_count"], 1)

    def test_operator_filter_applies_to_local_map_rows(self):
        response = self.client.get(reverse("base_links:map-aggregates"), {"operator": "999999"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source_total"], 1)
        self.assertEqual(response.json()["filtered_source_total"], 0)
        self.assertEqual(response.json()["states"], {})

    def test_custom_scope_does_not_leak_link_or_ticket(self):
        outside_operator = CMDBOperatorMirror.objects.create(source_config_item_id="map-out-op", name="Outside")
        CMDBLinkMirror.objects.create(source_config_item_id="map-out-ci", state="RJ", operator=outside_operator, legacy_project="Outside")
        group = self.user.groups.get(name="Analista NOC")
        scope = group.data_scope
        scope.mode = GroupDataScope.Mode.CUSTOM
        scope.save()
        scope.allowed_operators.set([Operadora.objects.create(name=self.operator.name, normalized_name=self.operator.name.casefold())])
        scope.allowed_projects.set([])
        response = self.client.get(reverse("base_links:map-aggregates"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source_total"], 0)
        self.assertNotIn("RJ", response.json()["states"])
