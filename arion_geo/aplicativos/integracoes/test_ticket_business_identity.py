from django.test import SimpleTestCase

from .services.ticket_business_identity import TicketBusinessIdentityService


class TicketBusinessIdentityTests(SimpleTestCase):
    def test_parses_operational_title_without_mutating_link_identity(self):
        result = TicketBusinessIdentityService.parse(
            "Ticket#2026102336000564 — BRAD - TELEFONICA BRASIL S.A. - RESTAURAÇÃO - "
            "INTERNET - BRADESCO - BD0001234 - BRAD: 1727"
        )
        self.assertEqual(result.client_raw, "TELEFONICA BRASIL S.A.")
        self.assertEqual(result.client, "Vivo")
        self.assertEqual(result.project, "Bradesco")
        self.assertEqual(result.occurrence, "Restauração")
        self.assertEqual(result.service, "Internet")
        self.assertEqual(result.business_id, "BD0001234")
        self.assertEqual(result.source, "OTRS_EXPLICIT_CLIENT")

    def test_carrefour_project_rule_supplies_claro_only_without_explicit_client(self):
        result = TicketBusinessIdentityService.parse(
            "Restauração - Internet - PROJETO CARREFOUR - BD1000000099501 - CI: 123"
        )
        self.assertEqual((result.client, result.project), ("Claro", "Carrefour"))
        self.assertEqual(result.source, "OTRS_PROJECT_RULE")

    def test_explicit_client_wins_and_bradesco_does_not_infer(self):
        claro = TicketBusinessIdentityService.parse("TELMEX - BRADESCO - BD1000001")
        unknown = TicketBusinessIdentityService.parse("BRADESCO - BD1000001")
        self.assertEqual((claro.client, claro.project), ("Claro", "Bradesco"))
        self.assertEqual((unknown.client, unknown.project), ("", "Bradesco"))

    def test_telmex_context_and_region_prefix_do_not_become_projects(self):
        claro_telmex = TicketBusinessIdentityService.parse("CLARO - TELMEX - BRADESCO - BD000123")
        telmex = TicketBusinessIdentityService.parse("TELMEX - CLARO.BA.BLIVR000123")
        self.assertEqual((claro_telmex.client_raw, claro_telmex.client, claro_telmex.project),
                         ("CLARO / TELMEX", "Claro", "Bradesco"))
        self.assertEqual((telmex.client, telmex.project), ("Claro", ""))
        vivo = TicketBusinessIdentityService.parse("TELEFONICA - BRADESCO - BD000124")
        self.assertEqual((vivo.client, vivo.project), ("Vivo", "Bradesco"))
