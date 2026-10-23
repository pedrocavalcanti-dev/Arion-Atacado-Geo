from datetime import date, datetime, timezone as datetime_timezone
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.conf import settings
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from unittest.mock import patch
from aplicativos.configuracoes.models import GroupDataScope
from aplicativos.base_links.models import Operadora
from aplicativos.integracoes.models import CMDBLinkMirror, CMDBOperatorMirror, OTRSTicket, OTRSTicketConfigItem
from aplicativos.integracoes.services.analytics import TicketQueryService
from aplicativos.integracoes.services.semantics import LinkSemantics
from .services.analytics import AnalyticsQueryService, DashboardAnalyticsService


class MirrorAnalyticsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="analytics-user", password="safe-password-1")
        group = Group.objects.get(name="Analista NOC")
        self.user.groups.set([group])
        scope, _ = GroupDataScope.objects.get_or_create(group=group)
        scope.mode = GroupDataScope.Mode.ALL
        scope.save()
        self.operator = CMDBOperatorMirror.objects.create(source_config_item_id="analytics-op", name="Operadora Analytics")
        self.link = CMDBLinkMirror.objects.create(source_config_item_id="analytics-ci-1", source_number="AN-1", state="SP", city="Sao Paulo", operator=self.operator, legacy_project="Projeto A", isp_raw="ISP real")
        self.other_link = CMDBLinkMirror.objects.create(source_config_item_id="analytics-ci-2", source_number="AN-2", state="RJ", operator=self.operator, legacy_project="Projeto A", isp_raw="ISP real")
        self.client.force_login(self.user)

    def _ticket(self, ext, status, open_state, day):
        return OTRSTicket.objects.create(external_id=ext, ticket_number=f"A-{ext}", queue_external_id=107, queue_name="NOC - ATACADO", external_state_id=ext, external_state_name=status, business_status=status, is_business_open=open_state, priority_name="3 normal", service_name="Internet", sla_name="Resposta NOC", source_created_at=datetime(2026, 10, day, tzinfo=datetime_timezone.utc))

    def test_dashboard_renders_real_snapshot_and_period(self):
        ticket = self._ticket(101, "OPEN", True, 5)
        OTRSTicketConfigItem.objects.create(ticket=ticket, config_item_id="analytics-ci-1", cmdb_link=self.link, relation_type="DependsOn", relation_state="Valid")
        response = self.client.get(reverse("dashboard"), {"date_from": "2026-10-01", "date_to": "2026-10-31"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_links"], 2)
        self.assertEqual(response.context["business_open"], 1)
        self.assertEqual(response.context["links_affected"], 1)
        self.assertContains(response, "Situação atual dos chamados")
        self.assertContains(response, "Em atendimento")
        self.assertNotContains(response, "OPEN")
        macro_counts = {item["name"]: item["value"] for item in response.context["macro_operators"]}
        self.assertEqual(macro_counts["OUTROS"], 2)
        self.assertEqual(response.context["macro_operator_coverage"], 0)

    def test_dashboard_period_and_snapshot_metrics_are_independent_and_noc_only(self):
        october_open = self._ticket(201, "OPEN", True, 5)
        october_pending = self._ticket(202, "PENDING", True, 8)
        september_resolved = self._ticket(203, "RESOLVED", False, 5)
        september_resolved.source_created_at = datetime(2026, 9, 5, tzinfo=datetime_timezone.utc)
        september_resolved.save()
        self._ticket(204, "CLOSED", False, 10)
        self._ticket(205, "CANCELED", False, 11)
        self._ticket(206, "UNKNOWN", False, 12)
        other_queue = self._ticket(207, "OPEN", True, 13)
        other_queue.queue_name = "OUTRA FILA"
        other_queue.save()
        invalid_state_link = CMDBLinkMirror.objects.create(
            source_config_item_id="analytics-invalid-state", state="N/A",
        )

        def relate(ticket, link, suffix):
            OTRSTicketConfigItem.objects.create(
                ticket=ticket, config_item_id=link.source_config_item_id,
                cmdb_link=link, relation_type=f"DependsOn-{suffix}", relation_state="Valid",
            )

        relate(october_open, self.link, "201")
        relate(october_pending, self.link, "202")
        relate(october_pending, self.other_link, "202")
        relate(september_resolved, self.other_link, "203")
        relate(other_queue, self.link, "207")

        with patch("aplicativos.integracoes.clients.cmdb.CMDBClient._post", side_effect=AssertionError("Dashboard não deve chamar ServiceUp")), patch(
            "aplicativos.integracoes.clients.otrs.OTRSReadOnlyClient._connection", side_effect=AssertionError("Dashboard não deve conectar ao MySQL OTRS")
        ), CaptureQueriesContext(connection) as queries:
            october = DashboardAnalyticsService.build(
                user=self.user, start=date(2026, 10, 1), end=date(2026, 10, 31),
            )
        self.assertLessEqual(len(queries), 20)
        self.assertEqual(october["calls"], 5)  # Tickets NOC sem relação também entram no volume.
        self.assertEqual(october["repeat"], 1)  # Somente o Link com dois Tickets distintos.
        self.assertEqual(october["monthly"][0]["calls"], 5)
        self.assertEqual(october["monthly"][0]["repeat"], 1)
        self.assertEqual(october["business_open"], 2)
        self.assertEqual(october["open_count"], 1)
        self.assertEqual(october["pending_count"], 1)
        self.assertEqual(october["resolved_count"], 1)
        self.assertEqual(october["closed_count"], 1)
        self.assertEqual(october["canceled_count"], 1)
        self.assertEqual(october["unknown_count"], 1)
        self.assertEqual(october["total_links"], 3)
        self.assertEqual(october["state_count"], 2)
        self.assertEqual([item["code"] for item in october["top_states"]], ["RJ", "SP"])

        september = DashboardAnalyticsService.build(
            user=self.user, start=date(2026, 9, 1), end=date(2026, 9, 30),
        )
        self.assertEqual(september["calls"], 1)
        self.assertEqual(september["repeat"], 0)
        self.assertEqual(september["monthly"][0]["calls"], 1)
        self.assertEqual(september["business_open"], october["business_open"])
        self.assertEqual(september["open_count"], october["open_count"])
        self.assertEqual(september["pending_count"], october["pending_count"])
        self.assertEqual(september["resolved_count"], october["resolved_count"])
        self.assertEqual(september["closed_count"], october["closed_count"])
        self.assertEqual(september["canceled_count"], october["canceled_count"])
        self.assertEqual(september["total_links"], october["total_links"])
        self.assertEqual(september["state_count"], october["state_count"])
        rendered = self.client.get(reverse("dashboard"), {
            "date_from": "2026-09-01", "date_to": "2026-09-30",
        })
        self.assertContains(rendered, "Não classificados")
        self.assertNotContains(rendered, "UNKNOWN")

    def test_unknown_ticket_status_is_hidden_when_zero(self):
        response = self.client.get(reverse("dashboard"), {
            "date_from": "2026-10-01", "date_to": "2026-10-31",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["unknown_count"], 0)
        self.assertContains(response, "Chamados abertos agora")
        self.assertContains(response, "Em atendimento + pendentes")
        self.assertNotContains(response, "Não classificados")
        self.assertNotContains(response, "Prioridade, serviço e SLA")
        self.assertNotContains(response, "Tickets por data de criação")
        self.assertNotContains(response, "Distribuição por provedor")

    def test_dashboard_macro_operator_uses_persisted_legacy_mapping_not_local_isp(self):
        self.link.legacy_operator_classification = CMDBLinkMirror.LegacyOperator.VIVO
        self.link.save(update_fields=("legacy_operator_classification",))
        self.other_link.legacy_operator_classification = CMDBLinkMirror.LegacyOperator.CLARO
        self.other_link.save(update_fields=("legacy_operator_classification",))
        self.operator.name = "FIERCE TELECOM"
        self.operator.save()

        result = DashboardAnalyticsService.build(
            user=self.user, start=date(2026, 10, 1), end=date(2026, 10, 31),
        )
        counts = {item["name"]: item["value"] for item in result["macro_operators"]}
        self.assertEqual(counts, {"VIVO": 1, "CLARO": 1, "ALGAR": 0, "OUTROS": 0})
        self.assertEqual(result["macro_operator_coverage"], 100)

    def test_link_semantics_resolve_provider_name_and_keep_ids_technical(self):
        self.operator.source_config_item_id = "6804"
        self.operator.name = "CLARO"
        self.operator.save()
        self.link.isp_raw = "6804"
        self.link.save()
        semantic = LinkSemantics.from_link(self.link)
        self.assertEqual(semantic.provider_name, "CLARO")
        self.assertNotEqual(semantic.provider_name, "6804")
        self.assertEqual(semantic.provider_config_item_id, "6804")
        self.assertIsNone(semantic.project_name)
        self.assertIsNone(semantic.contract_operator_name)

    def test_unresolved_numeric_isp_is_never_a_provider_label(self):
        self.link.operator = None
        self.link.isp_raw = "10097"
        self.link.save()
        semantic = LinkSemantics.from_link(self.link)
        self.assertEqual(semantic.provider_name, "Não classificado")
        self.assertEqual(semantic.provider_config_item_id, "10097")
        self.assertEqual(semantic.isp_raw, "10097")

    def test_cockpit_provider_options_use_names_not_raw_config_item_ids(self):
        self.operator.source_config_item_id = "6804"
        self.operator.name = "CLARO"
        self.operator.save()
        self.link.isp_raw = "6804"
        self.link.save()
        result = AnalyticsQueryService().query({
            "metric": "links", "group_by": "provider", "period_from": "2026-10",
            "period_to": "2026-10", "period": "2026-10", "filters": {},
        }, user=self.user)
        self.assertEqual(result["options"]["provider"], ["CLARO"])
        self.assertEqual(result["breakdown"][0]["key"], "CLARO")
        self.assertNotIn("6804", result["options"]["provider"])

    def test_noc_period_and_current_backlog_have_separate_date_semantics(self):
        september = self._ticket(111, "CLOSED", False, 5)
        september.source_created_at = datetime(2026, 9, 5, tzinfo=datetime_timezone.utc)
        september.save()
        october_open = self._ticket(112, "OPEN", True, 5)
        october_pending = self._ticket(113, "PENDING", True, 8)
        october_resolved = self._ticket(114, "RESOLVED", False, 9)
        other_queue = self._ticket(115, "OPEN", True, 9)
        other_queue.queue_name = "OUTRA FILA"
        other_queue.save()
        october_closed = self._ticket(116, "CLOSED", False, 10)
        october_canceled = self._ticket(117, "CANCELED", False, 11)
        for ticket in (september, october_open, october_pending, october_resolved, other_queue, october_closed, october_canceled):
            OTRSTicketConfigItem.objects.create(ticket=ticket, config_item_id=self.link.source_config_item_id, cmdb_link=self.link, relation_type="DependsOn", relation_state="Valid")
        self.assertFalse(TicketQueryService.noc_tickets().filter(pk=other_queue.pk).exists())
        payload = {"period_from": "2026-09", "period_to": "2026-10", "period": "2026-09", "filters": {}, "group_by": "status"}
        service = AnalyticsQueryService()
        created = service.query({**payload, "metric": "tickets"}, user=self.user)
        backlog = service.query({**payload, "metric": "backlog"}, user=self.user)
        self.assertEqual(created["value"], 1)
        self.assertEqual(backlog["value"], 2)
        self.assertTrue(backlog["meta"]["backlog_is_current_snapshot"])

    def test_main_pages_render_without_known_encoding_damage(self):
        routes = ("dashboard", "cockpit", "mapa:index", "base_links:index", "rankings:index")
        damaged = ("per?odo", "cria??o", "Servi?o", "n?o", "reconstr?i", "hist?rico", "m?trica", "integra??o", "\ufffd", "Ãƒ")
        admin = get_user_model().objects.create_superuser(username="encoding-smoke", email="", password="safe-password-123")
        self.client.force_login(admin)
        for route in routes:
            response = self.client.get(reverse(route))
            self.assertEqual(response.status_code, 200, route)
            body = response.content.decode("utf-8")
            for token in damaged:
                self.assertNotIn(token, body, f"{route}: {token}")
        cockpit_script = (Path(settings.BASE_DIR) / "static" / "js" / "painel" / "cockpit.js").read_text(encoding="utf-8")
        for token in ("servi?o", "per?odo", "Reincid?ncia", "\ufffd", "Ãƒ"):
            self.assertNotIn(token, cockpit_script)

    def test_analytics_uses_real_distinct_tickets_and_supported_dimensions(self):
        ticket = self._ticket(102, "OPEN", True, 5)
        for link in (self.link, self.other_link):
            OTRSTicketConfigItem.objects.create(ticket=ticket, config_item_id=link.source_config_item_id, cmdb_link=link, relation_type="DependsOn", relation_state="Valid")
        base = {"period_from": "2026-10", "period_to": "2026-10", "period": "2026-10", "filters": {}}
        service = AnalyticsQueryService()
        result = service.query({**base, "metric": "tickets", "group_by": "operator"}, user=self.user)
        self.assertEqual(result["source"], "real")
        self.assertEqual(result["value"], 1)
        self.assertEqual(result["meta"]["demo"], False)
        self.assertEqual(result["breakdown"][0]["value"], 1)

    def test_analytics_rejects_unsupported_synthetic_sla_metrics(self):
        service = AnalyticsQueryService()
        with self.assertRaises(ValueError):
            service.query({"metric": "sla_met", "group_by": "operator", "period_from": "2026-10", "period_to": "2026-10", "period": "2026-10", "filters": {}}, user=self.user)

    def test_custom_scope_excludes_unlinked_tickets(self):
        unlinked = self._ticket(103, "OPEN", True, 5)
        group = self.user.groups.get(name="Analista NOC")
        scope = group.data_scope
        scope.mode = GroupDataScope.Mode.CUSTOM
        scope.save()
        scope.allowed_operators.set([Operadora.objects.create(name=self.operator.name, normalized_name=self.operator.name.casefold())])
        scope.allowed_projects.set([])
        from aplicativos.integracoes.services.analytics import TicketQueryService
        self.assertFalse(TicketQueryService.base(self.user).filter(pk=unlinked.pk).exists())

    def test_cockpit_export_uses_the_same_real_mirror_query(self):
        ticket = self._ticket(105, "OPEN", True, 5)
        OTRSTicketConfigItem.objects.create(ticket=ticket, config_item_id="analytics-ci-1", cmdb_link=self.link, relation_type="DependsOn", relation_state="Valid")
        payload = {"format": "csv", "metric": "tickets", "group_by": "operator", "period_from": "2026-10", "period_to": "2026-10", "period": "2026-10", "filters": {}}
        response = self.client.post(reverse("analytics-export"), data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("Operadora Analytics", response.content.decode("utf-8-sig"))
        self.assertNotIn("Demo", response.content.decode("utf-8-sig"))

    def test_cockpit_api_uses_real_query_and_rejects_bad_payload(self):
        ticket = self._ticket(104, "OPEN", True, 5)
        OTRSTicketConfigItem.objects.create(ticket=ticket, config_item_id="analytics-ci-1", cmdb_link=self.link, relation_type="DependsOn", relation_state="Valid")
        response = self.client.post(reverse("analytics-query"), data=json.dumps({"metric":"tickets", "group_by":"status", "period_from":"2026-10", "period_to":"2026-10", "period":"2026-10", "filters":{}}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["value"], 1)
        invalid = self.client.post(reverse("analytics-query"), data="[]", content_type="application/json")
        self.assertEqual(invalid.status_code, 400)
