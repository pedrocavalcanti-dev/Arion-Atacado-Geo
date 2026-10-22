from pathlib import Path
import json
from io import BytesIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from aplicativos.base_links.models import CMDBImport, CMDBLink, Operadora, Projeto, Provider
from aplicativos.configuracoes.models import UserDataScope
from aplicativos.painel.models import SavedAnalyticsView
from aplicativos.painel.services.analytics import AnalyticsQueryService
from aplicativos.painel.views import STATE_NAMES
from django.utils import timezone


class OverviewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="overview-user", password="Senha-segura-123")
        self.client.force_login(self.user)

    def test_overview_is_a_contextual_entry_point_with_real_cmdb_summary_and_module_actions(self):
        batch = CMDBImport.objects.create(filename="cmdb.xlsx", file_sha256="a" * 64, imported_by=self.user)
        operator = Operadora.objects.create(name="Claro", normalized_name="claro")
        project = Projeto.objects.create(name="Bradesco", normalized_name="bradesco")
        provider = Provider.objects.create(name="ISP Real", normalized_name="isp-real")
        CMDBLink.objects.create(config_item_id="home-1", uf="SP", operadora=operator, projeto=project, provider=provider, last_seen_import=batch)
        CMDBLink.objects.create(config_item_id="home-2", uf="MG", operadora=operator, projeto=project, provider=provider, last_seen_import=batch)
        response = self.client.get(reverse("painel:index"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_links"], 2)
        self.assertEqual(response.context["state_count"], 2)
        self.assertEqual(response.context["provider_count"], 1)
        self.assertContains(response, timezone.localtime(batch.created_at).strftime("%d/%m/%Y %H:%M"))
        for route in ("base_links:index", "cockpit", "mapa:index"):
            self.assertContains(response, f'href="{reverse(route)}"')
        for label in ("Pesquisar um link", "Investigar a operação", "Explorar geograficamente"):
            self.assertContains(response, label)
        overview = response.content.decode().split('<section class="overview-page"', 1)[1].split("</section>", 1)[0]
        for excluded in ("Ver dashboard", "Rankings", "Chamados", "Reincidentes", "SLA", "gráfico mensal", "Pergunte ao Arion"):
            self.assertNotIn(excluded, overview)

    def test_overview_respects_operator_and_project_data_scope_intersection(self):
        batch = CMDBImport.objects.create(filename="cmdb.xlsx", file_sha256="b" * 64, imported_by=self.user)
        claro = Operadora.objects.create(name="Claro", normalized_name="claro")
        vivo = Operadora.objects.create(name="Vivo", normalized_name="vivo")
        bradesco = Projeto.objects.create(name="Bradesco", normalized_name="bradesco")
        outro = Projeto.objects.create(name="Outro", normalized_name="outro")
        provider = Provider.objects.create(name="ISP permitido", normalized_name="isp-permitido")
        outside_provider = Provider.objects.create(name="ISP fora do escopo", normalized_name="isp-fora")
        CMDBLink.objects.create(config_item_id="home-scope-1", uf="SP", operadora=claro, projeto=bradesco, provider=provider, last_seen_import=batch)
        CMDBLink.objects.create(config_item_id="home-scope-2", uf="RJ", operadora=claro, projeto=outro, provider=outside_provider, last_seen_import=batch)
        CMDBLink.objects.create(config_item_id="home-scope-3", uf="MG", operadora=vivo, projeto=bradesco, provider=outside_provider, last_seen_import=batch)
        scope = UserDataScope.objects.create(user=self.user, mode=UserDataScope.Mode.CUSTOM)
        scope.allowed_operators.set([claro])
        scope.allowed_projects.set([bradesco])
        response = self.client.get(reverse("painel:index"))
        self.assertEqual(response.context["total_links"], 1)
        self.assertEqual(response.context["state_count"], 1)
        self.assertEqual(response.context["provider_count"], 1)

    def test_overview_handles_empty_cmdb_without_import(self):
        response = self.client.get(reverse("painel:index"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_links"], 0)
        self.assertEqual(response.context["state_count"], 0)
        self.assertEqual(response.context["provider_count"], 0)
        self.assertContains(response, "Nenhuma importação registrada")


class DashboardAndFlagsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="noc-exec", password="Senha-segura-123")
        self.client.force_login(self.user)

    def test_all_state_flags_exist_locally(self):
        flags_dir = Path(settings.BASE_DIR) / "static" / "imagens" / "bandeiras" / "estados"
        self.assertEqual(len(STATE_NAMES), 27)
        for code in STATE_NAMES:
            self.assertGreater((flags_dir / f"{code.lower()}.svg").stat().st_size, 150)

    def test_dashboard_renders_executive_reading(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visão da operação")
        self.assertContains(response, "Chamados demonstrativos")
        self.assertContains(response, "Demo")
        self.assertNotContains(response, "Minhas visões")

    def test_dashboard_and_cockpit_routes_are_separate(self):
        dashboard = self.client.get(reverse("dashboard"))
        cockpit = self.client.get(reverse("cockpit"))
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(cockpit.status_code, 200)
        self.assertContains(cockpit, 'data-cockpit')
        self.assertContains(cockpit, 'data-query-url="/api/analytics/query/"')

    def test_dashboard_uses_real_facets_and_the_cockpit_demo_series(self):
        claro = Operadora.objects.create(name="Claro", normalized_name="claro")
        provider = Provider.objects.create(name="ISP Real", normalized_name="isp-real")
        CMDBLink.objects.create(config_item_id="db-1", uf="SP", operadora=claro, provider=provider)
        CMDBLink.objects.create(config_item_id="db-2", uf="MG")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.context["total_links"], 2)
        self.assertEqual(response.context["state_count"], 2)
        self.assertEqual(response.context["provider_count"], 1)
        self.assertEqual(sum(item["value"] for item in response.context["operators"]), 2)
        self.assertIn("Não classificado", [item["name"] for item in response.context["operators"]])
        self.assertContains(response, "ISP Real")
        api_result = AnalyticsQueryService().query({"metric": "tickets", "group_by": "reason", "period": "2026-10", "filters": {}})
        self.assertEqual(response.context["calls"], api_result["value"])
        self.assertEqual(response.context["monthly"][-1]["calls"], api_result["value"])


class AnalyticsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="analytics", password="Senha-segura-123")
        self.client.force_login(self.user)
        operator = Operadora.objects.create(name="Claro", normalized_name="claro")
        project = Projeto.objects.create(name="Bradesco", normalized_name="bradesco")
        provider = Provider.objects.create(name="ISP Norte", normalized_name="isp-norte")
        CMDBLink.objects.create(config_item_id="AN-1", uf="SP", operadora=operator, projeto=project, provider=provider)

    def test_demo_is_deterministic_and_filters(self):
        query = {"metric": "tickets", "group_by": "reason", "period": "2026-10", "compare_to": "2026-01", "filters": {"operator": "Claro", "project": "Bradesco", "provider": "ISP Norte", "uf": "SP", "reason": "Pendência Financeira"}}
        service = AnalyticsQueryService()
        self.assertEqual(service.query(query), service.query(query))

    def test_operational_metric_invariants_and_group_totals(self):
        service = AnalyticsQueryService()
        base = {"period": "2026-10", "filters": {}}
        values = {metric: service.query({**base, "metric": metric, "group_by": "operator"}) for metric in ("tickets", "open_tickets", "closed_tickets", "recurrences", "sla_met", "sla_missed", "backlog")}
        tickets = values["tickets"]["value"]
        self.assertLessEqual(values["open_tickets"]["value"], tickets)
        self.assertLessEqual(values["closed_tickets"]["value"], tickets)
        self.assertEqual(values["open_tickets"]["value"] + values["closed_tickets"]["value"], tickets)
        self.assertLessEqual(values["recurrences"]["value"], tickets)
        self.assertLessEqual(values["sla_met"]["value"] + values["sla_missed"]["value"], tickets)
        self.assertTrue(all(item["value"] >= 0 for item in values.values()))
        links = service.query({**base, "metric": "links", "group_by": "operator"})
        self.assertLessEqual(sum(row["value"] for row in links["breakdown"]), links["value"])
        zero = service.query({**base, "metric": "tickets", "period": "2026-01", "compare_to": "2026-01", "filters": {"uf": "XX"}})
        self.assertNotIn(float("inf"), [zero["comparison"]["percent"] or 0])
        ranged = service.query({"metric": "tickets", "period": "2026-10", "period_from": "2026-01", "period_to": "2026-10"})
        self.assertEqual([row["key"] for row in ranged["series"]][0], "2026-01")
        self.assertEqual(len(ranged["series"]), 10)

    def test_metric_dimension_and_filter_whitelists(self):
        service = AnalyticsQueryService()
        with self.assertRaises(ValueError): service.query({"metric": "__import__", "group_by": "month"})
        with self.assertRaises(ValueError): service.query({"metric": "tickets", "group_by": "source_payload"})
        with self.assertRaises(ValueError): service.query({"metric": "links", "group_by": "reason"})
        with self.assertRaises(ValueError): service.query({"metric": "links", "filters": {"sql": "DROP TABLE"}})

    def test_endpoint_requires_login_and_returns_real_links(self):
        self.client.logout()
        response = self.client.post(reverse("analytics-query"), data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 302)
        self.client.force_login(self.user)
        response = self.client.post(reverse("analytics-query"), data='{"metric":"links","group_by":"uf","period":"2026-10"}', content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["value"], 1)

    def test_saved_views_are_private(self):
        SavedAnalyticsView.objects.create(user=self.user, name="SP", configuration={"metric": "links"})
        other = get_user_model().objects.create_user(username="other", password="Senha-segura-123")
        self.client.force_login(other)
        response = self.client.post(reverse("analytics-saved-views"), data='{"action":"list"}', content_type="application/json")
        self.assertEqual(response.json()["views"], [])

    def test_quick_query_manual_filter_and_clear_sequence_uses_consistent_query_state(self):
        service = AnalyticsQueryService()
        sequence = [
            {"metric": "tickets", "group_by": "reason", "filters": {"reason": "Pendência Financeira"}},
            {"metric": "recurrences", "group_by": "operator", "filters": {}},
            {"metric": "backlog", "group_by": "operator", "filters": {}},
            {"metric": "tickets", "group_by": "reason", "filters": {}},
            {"metric": "links", "group_by": "uf", "filters": {"uf": "SP"}},
            {"metric": "tickets", "group_by": "reason", "filters": {}},
            {"metric": "sla_missed", "group_by": "provider", "filters": {}},
        ]
        results = [service.query({"period": "2026-10", "period_from": "2026-01", "period_to": "2026-10", **state}, user=self.user) for state in sequence]
        self.assertEqual(results[1]["metric"], "recurrences")
        self.assertEqual(results[2]["metric"], "backlog")
        self.assertEqual(results[3]["value"], results[5]["value"])
        self.assertEqual(results[3]["breakdown"], results[5]["breakdown"])
        self.assertEqual(results[4]["group_by"], "uf")
        self.assertEqual(results[6]["group_by"], "provider")
        self.assertTrue(all(result["kpis"] and "detail" in result for result in results))

    def test_saved_view_can_be_renamed_only_by_its_owner(self):
        saved = SavedAnalyticsView.objects.create(user=self.user, name="Original", configuration={"metric": "tickets"})
        SavedAnalyticsView.objects.create(user=self.user, name="Nome ocupado", configuration={"metric": "links"})
        response = self.client.post(reverse("analytics-saved-views"), data='{"action":"rename","id":%d,"name":"Nova consulta"}' % saved.pk, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        saved.refresh_from_db()
        self.assertEqual(saved.name, "Nova consulta")
        response = self.client.post(reverse("analytics-saved-views"), data='{"action":"rename","id":%d,"name":"Nome ocupado"}' % saved.pk, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        response = self.client.post(reverse("analytics-saved-views"), data="[]", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        other = get_user_model().objects.create_user(username="rename-other", password="Senha-segura-123")
        self.client.force_login(other)
        response = self.client.post(reverse("analytics-saved-views"), data='{"action":"rename","id":%d,"name":"Invadida"}' % saved.pk, content_type="application/json")
        self.assertEqual(response.status_code, 404)
        saved.refresh_from_db()
        self.assertEqual(saved.name, "Nova consulta")

    def test_exports_use_query_state_and_current_data_scope(self):
        outside_operator = Operadora.objects.create(name="Fora do escopo", normalized_name="fora")
        outside_project = Projeto.objects.create(name="Projeto privado", normalized_name="privado")
        CMDBLink.objects.create(config_item_id="AN-OUT", uf="RJ", operadora=outside_operator, projeto=outside_project)
        scope = UserDataScope.objects.create(user=self.user, mode=UserDataScope.Mode.CUSTOM)
        scope.allowed_operators.set([Operadora.objects.get(name="Claro")])
        scope.allowed_projects.set([Projeto.objects.get(name="Bradesco")])
        payload = {"metric": "links", "group_by": "uf", "period": "2026-10", "period_from": "2026-01", "period_to": "2026-10", "filters": {}, "format": "csv"}
        expected = {
            "csv": ("text/csv", "arion-cockpit.csv"),
            "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "arion-cockpit.xlsx"),
            "pdf": ("application/pdf", "arion-cockpit.pdf"),
        }
        for file_format, (content_type, filename) in expected.items():
            payload["format"] = file_format
            response = self.client.post(reverse("analytics-export"), data=json.dumps(payload), content_type="application/json")
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response["Content-Type"].startswith(content_type))
            self.assertIn(filename, response["Content-Disposition"])
            if file_format == "csv":
                content = response.content.decode("utf-8-sig")
                self.assertIn("SP", content)
                self.assertNotIn("RJ", content)
                self.assertNotIn("Projeto privado", content)
            elif file_format == "xlsx":
                workbook = load_workbook(BytesIO(response.content), read_only=True)
                values = [cell for row in workbook["Dados"].iter_rows(values_only=True) for cell in row]
                self.assertIn("SP", values)
                self.assertNotIn("RJ", values)
            else:
                self.assertTrue(response.content.startswith(b"%PDF-1.4"))
                self.assertTrue(response.content.rstrip().endswith(b"%%EOF"))
                self.assertGreater(len(response.content), 2500)
                self.assertIn(b"ARION ATACADO GEO", response.content)
                self.assertIn(b"DETALHAMENTO", response.content)
                self.assertIn(b"SP", response.content)
                self.assertNotIn(b"RJ", response.content)
