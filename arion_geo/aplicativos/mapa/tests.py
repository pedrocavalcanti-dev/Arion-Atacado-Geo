from datetime import date, datetime, timezone as datetime_timezone
from html.parser import HTMLParser
from pathlib import Path
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse

from aplicativos.base_links.models import Operadora, Projeto
from aplicativos.configuracoes.models import GroupDataScope
from aplicativos.integracoes.models import CMDBLinkMirror, CMDBOperatorMirror, OTRSTicket, OTRSTicketConfigItem
from aplicativos.mapa.services.analytics import _bounds


class _MapDOMContractParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.classes = set()
        self.attributes = set()
        self.values = {}
        self.elements = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        self.attributes.update(attributes)
        for name, value in attrs:
            if value is not None:
                self.values.setdefault(name, set()).add(value)
        if attributes.get("id"):
            self.ids.add(attributes["id"])
        self.classes.update(attributes.get("class", "").split())
        self.elements.append((tag, attributes))


class MapMirrorTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="map-user", password="safe-password-1")
        group = Group.objects.get(name="Analista NOC")
        self.user.groups.set([group])
        scope, _ = GroupDataScope.objects.get_or_create(group=group)
        scope.mode = GroupDataScope.Mode.ALL
        scope.save()
        self.provider = CMDBOperatorMirror.objects.create(source_config_item_id="map-op", name="FIERCE TELECOM")
        self.link = CMDBLinkMirror.objects.create(
            source_config_item_id="map-ci", source_number="MAP-1", name="CLARO - BRADESCO - BD100000107001",
            state="SP", city="Sao Paulo", operator=self.provider, legacy_project="legacy frozen",
            contracting_client_raw="CLARO", contracting_client="Claro", business_project="BRADESCO",
            business_id="BD100000107001", business_identity_confidence="HIGH",
        )
        self.client.force_login(self.user)

    def _ticket(self, external_id, status, day=5, reason=""):
        stamp = datetime(2026, 10, day, tzinfo=datetime_timezone.utc)
        return OTRSTicket.objects.create(
            external_id=external_id, ticket_number=f"MAP-{external_id}", queue_external_id=107,
            queue_name="NOC - ATACADO", external_state_id=external_id, external_state_name=status,
            business_status=status, is_business_open=status in {"OPEN", "PENDING", "SCHEDULED"},
            source_created_at=stamp,
            terminal_state_at=stamp if status in {"RESOLVED", "CLOSED"} else None,
            closing_code_raw=reason,
        )

    def _relate(self, ticket, link=None):
        link = link or self.link
        return OTRSTicketConfigItem.objects.create(
            ticket=ticket, config_item_id=link.source_config_item_id, cmdb_link=link,
            relation_type="DependsOn", relation_state="Valid",
        )

    @override_settings(MAPBOX_PUBLIC_TOKEN="")
    def test_map_uses_local_mirror_and_restores_real_exploration_structure(self):
        response = self.client.get(reverse("mapa:index"))
        self.assertEqual(response.status_code, 200)
        for content in (
            "Visão geográfica", "data-mode=\"projects\"", "data-mode=\"calls\"",
            "data-mode=\"repeat\"", "data-mode=\"motives\"", "data-client=\"Claro\"",
            "data-client=\"Vivo\"", "data-client=\"Algar\"", "data-client=\"other\"",
            "data-national-tab=\"ranking\"", "data-national-tab=\"distribution\"", "data-state-panel",
        ):
            self.assertContains(response, content)
        self.assertContains(response, 'data-token=""')
        self.assertNotContains(response, "data/demo/")
        self.assertContains(response, "data-api-url")
        self.assertContains(response, "js/mapa/mapa-real.js")

    def test_map_template_matches_required_javascript_dom_selectors(self):
        response = self.client.get(reverse("mapa:index"))
        self.assertEqual(response.status_code, 200)
        parser = _MapDOMContractParser()
        parser.feed(response.content.decode("utf-8"))
        script = (settings.BASE_DIR / "static" / "js" / "mapa" / "mapa-real.js").read_text(encoding="utf-8")
        match = re.search(r"const required = \[(.*?)\];", script, re.DOTALL)
        self.assertIsNotNone(match, "mapa-real.js precisa declarar seus seletores DOM obrigatorios")
        selectors = re.findall(r'"([^"\\]+)"', match.group(1))
        self.assertTrue(selectors)
        for selector in selectors:
            if selector.startswith("#"):
                self.assertIn(selector[1:], parser.ids, f"ID ausente no template: {selector}")
            elif selector.startswith("["):
                attribute_match = re.fullmatch(r"\[([\w-]+)(?:=['\"]?([^'\"]+)['\"]?)?\]", selector)
                self.assertIsNotNone(attribute_match, f"Seletor nao coberto pelo teste: {selector}")
                attribute, value = attribute_match.groups()
                self.assertIn(attribute, parser.attributes, f"Atributo ausente no template: {selector}")
                if value:
                    self.assertIn(value, parser.values.get(attribute, set()), f"Valor ausente no template: {selector}")
        self.assertTrue({"base", "projects", "calls", "repeat", "motives"}.issubset(parser.values["data-mode"]))
        self.assertTrue({"all", "Claro", "Vivo", "Algar", "other"}.issubset(parser.values["data-client"]))
        self.assertTrue(any(tag == "label" and "data-period-control" in attrs for tag, attrs in parser.elements),
                        "O wrapper do periodo precisa manter o marcador data-period-control")
        self.assertTrue(any(tag == "select" and "data-period-filter" in attrs for tag, attrs in parser.elements))

    @override_settings(MAPBOX_PUBLIC_TOKEN="pk.test-token")
    def test_public_map_token_is_rendered_without_loading_demo_data(self):
        response = self.client.get(reverse("mapa:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-token="pk.test-token"')
        self.assertContains(response, "mapbox-gl-js/v3.33.0/mapbox-gl.js")

    def test_base_and_project_modes_use_parsed_client_project_and_real_provider(self):
        for mode in ("base", "projects"):
            data = self.client.get(reverse("base_links:map-aggregates"), {"mode": mode, "client": "Claro", "project": "BRADESCO"}).json()
            self.assertEqual(data["filtered_source_total"], 1)
            self.assertEqual(data["states"]["SP"]["total_links"], 1)
            self.assertEqual(data["states"]["SP"]["client_counts"], {"Claro": 1})
            self.assertEqual(data["states"]["SP"]["project_counts"], {"BRADESCO": 1})
            self.assertEqual(data["providers"][0]["name"], "FIERCE TELECOM")
        self.assertNotIn("legacy frozen", data["projects"])

    def test_telmex_is_canonical_claro_and_excluded_from_other(self):
        CMDBLinkMirror.objects.create(source_config_item_id="map-unknown-client", state="SP", contracting_client="")
        CMDBLinkMirror.objects.create(source_config_item_id="map-telmex-client", state="SP", contracting_client="TELMEX", business_project="BRADESCO")
        data = self.client.get(reverse("base_links:map-aggregates"), {"mode": "base", "client": "other"}).json()
        self.assertEqual(data["filtered_source_total"], 0)
        claro = self.client.get(reverse("base_links:map-aggregates"), {"mode": "base", "client": "Claro"}).json()
        self.assertEqual(claro["filtered_source_total"], 2)
        self.assertEqual(claro["states"]["SP"]["client_counts"], {"Claro": 2})
        all_data = self.client.get(reverse("base_links:map-aggregates"), {"mode": "base"}).json()
        self.assertEqual(all_data["states"]["SP"]["client_counts"]["Cliente não identificado"], 1)
        self.assertEqual(all_data["states"]["SP"]["client_coverage"], 66.7)

    def test_city_variants_are_aggregated_for_display_without_mutating_mirror(self):
        self.link.city = "GOIANIA"
        self.link.state = "GO"
        self.link.save(update_fields=("city", "state"))
        CMDBLinkMirror.objects.create(source_config_item_id="map-ci-go-2", state="GO", city="GOIÂNIA")
        CMDBLinkMirror.objects.create(source_config_item_id="map-ci-go-3", state="GO", city="Goiânia")
        data = self.client.get(reverse("base_links:map-aggregates"), {"mode": "base"}).json()
        self.assertEqual(data["states"]["GO"]["city_counts"], {"Goiânia": 3})
        self.link.refresh_from_db()
        self.assertEqual(self.link.city, "GOIANIA")

    def test_base_snapshot_ignores_period_and_calendar_month_period_is_supported(self):
        data = self.client.get(reverse("base_links:map-aggregates"), {"mode": "base", "period": "2026-10"}).json()
        self.assertEqual(data["period"], {"date_from": "", "date_to": ""})
        self.assertEqual(_bounds({"period": "2026-10"}), (date(2026, 10, 1), date(2026, 10, 31)))

    def test_map_detail_accepts_shareable_motive_url(self):
        ticket = self._ticket(88, "CLOSED", day=20, reason="FalhaMassiva")
        self._relate(ticket)
        response = self.client.get(reverse("base_links:map-state-detail"), {
            "mode": "motives", "uf": "SP", "reason": "FalhaMassiva", "period": "2026-10",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ticket_total"], 1)
        self.assertEqual(response.json()["tickets"][0]["closing_reason"], "FalhaMassiva")

    def test_ticket_drawer_detail_exposes_only_safe_ticket_context_and_title_identity(self):
        ticket = self._ticket(90, "CLOSED", day=20, reason="FalhaMassiva")
        ticket.title = "TELEFONICA BRASIL S.A. - RESTAURAÇÃO - INTERNET - BRADESCO - BD0001234"
        ticket.priority_name = "3 normal"
        ticket.customer_id = "private-customer-id"
        ticket.save(update_fields=("title", "priority_name", "customer_id"))
        self._relate(ticket)
        response = self.client.get(reverse("base_links:map-state-detail"), {
            "mode": "motives", "uf": "SP", "reason": "FalhaMassiva", "period": "2026-10",
        })
        self.assertEqual(response.status_code, 200)
        item = response.json()["tickets"][0]
        self.assertEqual(item["identity"]["client"], "Vivo")
        self.assertEqual(item["identity"]["project"], "Bradesco")
        self.assertEqual(item["identity"]["occurrence"], "Restauração")
        self.assertEqual(item["priority"], "3 normal")
        self.assertEqual(item["cmdb"]["config_item_id"], "map-ci")
        self.assertNotIn("customer_id", item)
        self.assertNotIn("article", item)

    def test_map_script_restores_shareable_filters_and_keeps_selected_uf_on_mode_switch(self):
        script = (settings.BASE_DIR / "static" / "js" / "mapa" / "mapa-real.js").read_text(encoding="utf-8")
        for token in (
            "new URLSearchParams(location.search)", "state.selectedUF=(initialParams.get(\"uf\")||\"\").toUpperCase()",
            "[\"mode\",\"client\",\"project\",\"period\",\"uf\",\"reason\",\"provider\",\"date_from\",\"date_to\",\"status\",\"priority\"]",
            "if (state.selectedUF) await loadState(state.selectedUF)",
            'const temporal=["calls","repeat","motives"].includes(state.mode);',
            'ui.reasonWrap.hidden=state.mode!=="motives";',
        ):
            self.assertIn(token, script)
        self.assertEqual(script.count("bind();initialize();"), 1)
        self.assertNotIn("DOMContentLoaded", script)

    def test_drawer_sections_are_mode_specific_and_hidden_when_empty(self):
        template = (settings.BASE_DIR / "templates" / "mapa" / "_cmdb.html").read_text(encoding="utf-8")
        script = (settings.BASE_DIR / "static" / "js" / "mapa" / "mapa-real.js").read_text(encoding="utf-8")
        for section in ("clients", "coverage", "projects", "providers", "cities", "reasons", "links", "tickets"):
            self.assertIn(f'data-panel-section="{section}"', template)
        self.assertIn("section.hidden=!sectionData[section.dataset.panelSection]", script)

    def test_calendar_month_period_filters_tickets_and_returns_month_dates(self):
        self._relate(self._ticket(89, "OPEN", day=20))
        data = self.client.get(reverse("base_links:map-aggregates"), {"mode": "calls", "period": "2026-10"}).json()
        self.assertEqual(data["ticket_count"], 1)
        self.assertEqual(data["period"], {"date_from": "2026-10-01", "date_to": "2026-10-31"})

    def test_ticket_mode_uses_explicit_ticket_client_for_ticket_distribution(self):
        ticket = self._ticket(91, "OPEN", day=20)
        ticket.title = "TELEFONICA BRASIL S.A. - BRADESCO - BD0001234"
        ticket.save(update_fields=("title",))
        self._relate(ticket)
        data = self.client.get(reverse("base_links:map-aggregates"), {
            "mode": "calls", "period": "2026-10",
        }).json()
        self.assertEqual(data["ticket_client_counts"], {"Vivo": 1})
        self.assertEqual(data["ticket_project_counts"], {"Bradesco": 1})
        filtered = self.client.get(reverse("base_links:map-aggregates"), {
            "mode": "calls", "period": "2026-10", "client": "Vivo", "project": "Bradesco",
        }).json()
        self.assertEqual(filtered["ticket_count"], 1)
        detail = self.client.get(reverse("base_links:map-state-detail"), {
            "mode": "calls", "period": "2026-10", "client": "Vivo", "project": "Bradesco", "uf": "SP",
        }).json()
        self.assertEqual(detail["ticket_total"], 1)

    def test_calls_status_and_priority_filters_are_scoped_and_return_options(self):
        first = self._ticket(92, "OPEN", day=20)
        first.priority_name = "3 normal"
        first.save(update_fields=("priority_name",))
        self._relate(first)
        second = self._ticket(93, "CLOSED", day=21)
        second.priority_name = "2 high"
        second.save(update_fields=("priority_name",))
        self._relate(second)
        data = self.client.get(reverse("base_links:map-aggregates"), {
            "mode": "calls", "period": "2026-10", "status": "OPEN", "priority": "3 normal",
        }).json()
        self.assertEqual(data["ticket_count"], 1)
        self.assertEqual(data["ticket_status_counts"], {"OPEN": 1})
        self.assertEqual(data["priority_options"], ["2 high", "3 normal"])

    def test_calls_deduplicate_tickets_per_state_and_exclude_canceled_unknown(self):
        second_sp = CMDBLinkMirror.objects.create(source_config_item_id="map-ci-sp-2", state="SP", contracting_client="Claro", business_project="BRADESCO")
        canceled_only = CMDBLinkMirror.objects.create(source_config_item_id="map-ci-rj", state="RJ", contracting_client="Claro", business_project="BRADESCO")
        statuses = ("OPEN", "PENDING", "SCHEDULED", "RESOLVED", "CLOSED", "CANCELED", "UNKNOWN")
        for external_id, status in enumerate(statuses, start=30):
            ticket = self._ticket(external_id, status)
            self._relate(ticket, canceled_only if status in {"CANCELED", "UNKNOWN"} else self.link)
            if status == "OPEN":
                self._relate(ticket, second_sp)
        data = self.client.get(reverse("base_links:map-aggregates"), {
            "mode": "calls", "period": "custom", "date_from": "2026-10-01", "date_to": "2026-10-31",
        }).json()
        self.assertEqual(data["ticket_count"], 5)
        self.assertEqual(data["active_ticket_count"], 3)
        self.assertEqual(data["states"]["SP"]["ticket_count"], 5)
        self.assertEqual(data["affected_link_count"], 2)
        self.assertEqual(data["states"]["SP"]["affected_links"], 2)
        self.assertEqual(data["states"]["SP"]["active_tickets"], 3)
        self.assertEqual(data["ticket_status_counts"], {"OPEN": 1, "PENDING": 1, "SCHEDULED": 1, "RESOLVED": 1, "CLOSED": 1})
        self.assertEqual(data["states"]["RJ"]["ticket_count"], 0)

    def test_repeat_mode_counts_distinct_links_with_two_valid_tickets(self):
        for external_id in (40, 41):
            self._relate(self._ticket(external_id, "RESOLVED"))
        data = self.client.get(reverse("base_links:map-aggregates"), {
            "mode": "repeat", "period": "custom", "date_from": "2026-10-01", "date_to": "2026-10-31",
        }).json()
        self.assertEqual(data["recurrence_link_count"], 1)
        self.assertEqual(data["recurrence_ticket_count"], 2)
        self.assertEqual(data["states"]["SP"]["recurrence_links"], 1)
        self.assertEqual(data["recurrence_client_counts"], {"Claro": 1})

    def test_motive_mode_uses_terminal_date_normalized_reason_and_valid_terminal_states(self):
        self._relate(self._ticket(50, "RESOLVED", day=10, reason="PendenciaFinanceira"))
        self._relate(self._ticket(51, "CLOSED", day=11, reason="Pendência Financeira"))
        self._relate(self._ticket(52, "CANCELED", day=12, reason="ChamadoCancelado"))
        data = self.client.get(reverse("base_links:map-aggregates"), {
            "mode": "motives", "period": "custom", "date_from": "2026-10-01", "date_to": "2026-10-31",
        }).json()
        reason = next(iter(data["states"]["SP"]["reason_counts"]))
        self.assertEqual(data["states"]["SP"]["reason_counts"][reason], 2)
        self.assertNotIn("ChamadoCancelado", data["states"]["SP"]["reason_counts"])

    def test_provider_filter_uf_normalization_and_invalid_provider_validation(self):
        CMDBLinkMirror.objects.create(source_config_item_id="map-ci-name-uf", state="São Paulo", operator=self.provider, contracting_client="Claro", business_project="BRADESCO")
        filtered = self.client.get(reverse("base_links:map-aggregates"), {"provider": self.provider.pk, "mode": "base"})
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(filtered.json()["filtered_source_total"], 2)
        self.assertEqual(filtered.json()["states"]["SP"]["total_links"], 2)
        invalid = self.client.get(reverse("base_links:map-aggregates"), {"provider": "not-an-id"})
        self.assertEqual(invalid.status_code, 400)

    def test_custom_scope_intersects_client_and_project_without_provider_confusion(self):
        outside_provider = CMDBOperatorMirror.objects.create(source_config_item_id="map-out-op", name="Outside ISP")
        CMDBLinkMirror.objects.create(source_config_item_id="map-out-ci", state="RJ", operator=outside_provider, contracting_client="Vivo", business_project="Outside")
        group = self.user.groups.get(name="Analista NOC")
        scope = group.data_scope
        scope.mode = GroupDataScope.Mode.CUSTOM
        scope.save()
        scope.allowed_operators.set([Operadora.objects.create(name="Claro", normalized_name="claro")])
        scope.allowed_projects.set([Projeto.objects.create(name="BRADESCO", normalized_name="bradesco")])
        data = self.client.get(reverse("base_links:map-aggregates"), {"mode": "base"}).json()
        self.assertEqual(data["source_total"], 1)
        self.assertEqual(data["states"]["SP"]["total_links"], 1)
        self.assertNotIn("RJ", data["states"])

    def test_state_detail_returns_links_and_ticket_rows_from_scoped_sources(self):
        self._relate(self._ticket(70, "OPEN"))
        response = self.client.get(reverse("base_links:map-state-detail"), {"uf": "SP", "mode": "calls", "period": "custom", "date_from": "2026-10-01", "date_to": "2026-10-31"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["links"][0]["provider"], "FIERCE TELECOM")
        self.assertEqual(response.json()["tickets"][0]["ticket_number"], "MAP-70")
        self.assertNotIn("subject", response.json()["tickets"][0])

    def test_superuser_bypasses_scope_using_existing_rule(self):
        CMDBLinkMirror.objects.create(source_config_item_id="map-out-ci", state="RJ", business_project="Outside")
        superuser = get_user_model().objects.create_superuser(username="map-root", email="", password="safe-password-2")
        self.client.force_login(superuser)
        data = self.client.get(reverse("base_links:map-aggregates"), {"mode": "base"}).json()
        self.assertEqual(data["source_total"], 2)
        self.assertEqual(data["states"]["RJ"]["total_links"], 1)
