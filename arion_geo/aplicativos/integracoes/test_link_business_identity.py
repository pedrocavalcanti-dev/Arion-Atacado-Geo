from django.test import SimpleTestCase, override_settings

from .services.link_business_identity import LinkBusinessIdentityService


class LinkBusinessIdentityTests(SimpleTestCase):
    def test_known_client_project_account_and_business_id(self):
        result = LinkBusinessIdentityService.parse("CLARO - DIVERSOS - NESTLÉ - BD200000111846")
        self.assertEqual(result.contracting_client_raw, "CLARO")
        self.assertEqual(result.contracting_client, "Claro")
        self.assertEqual(result.business_project, "Diversos")
        self.assertEqual(result.business_account, "NESTLÉ")
        self.assertEqual(result.business_id, "BD200000111846")
        self.assertEqual(result.confidence, "HIGH")
        self.assertEqual(result.source, "CMDB_EXPLICIT_CLIENT")

    def test_en_dash_em_dash_and_repeated_spaces_parse_equally(self):
        for name in (
            "VIVO - BRADESCO - BL100000077045",
            "VIVO – BRADESCO – BL100000077045",
            "VIVO —  BRADESCO  — BL100000077045",
        ):
            with self.subTest(name=name):
                result = LinkBusinessIdentityService.parse(name)
                self.assertEqual((result.contracting_client, result.business_project, result.business_id),
                                 ("Vivo", "Bradesco", "BL100000077045"))

    def test_project_without_account_and_without_business_id(self):
        with_id = LinkBusinessIdentityService.parse("CLARO - CORREIOS - BD100000107001")
        without_id = LinkBusinessIdentityService.parse("VIVO - ARCOS DOURADOS")
        self.assertEqual(with_id.business_project, "Correios")
        self.assertEqual(with_id.business_account, "")
        self.assertEqual(without_id.business_project, "Arcos Dourados")
        self.assertEqual(without_id.business_id, "")

    def test_unknown_multi_segment_prefix_is_not_guessed(self):
        result = LinkBusinessIdentityService.parse("UFINET - BD50000067605 - GOL LOG - AEROPORTO DE BELEM")
        self.assertEqual(result.contracting_client, "")
        self.assertEqual(result.business_project, "")
        self.assertEqual(result.business_account, "")
        self.assertEqual(result.business_id, "BD50000067605")
        self.assertEqual(result.confidence, "LOW")

    def test_raw_client_is_preserved_and_aliases_are_configurable_only(self):
        raw = LinkBusinessIdentityService.parse("TELMEX - BRADESCO - BD50000082150")
        aliased = LinkBusinessIdentityService.parse(
            "TELMEX - BRADESCO - BD50000082150", aliases={"TELMEX": "Claro"},
        )
        self.assertEqual(raw.contracting_client_raw, "TELMEX")
        self.assertEqual(raw.contracting_client, "Claro")
        self.assertEqual(aliased.contracting_client_raw, "TELMEX")
        self.assertEqual(aliased.contracting_client, "Claro")
        self.assertEqual(aliased.business_project, "Bradesco")

    def test_confirmed_exclusive_project_rules_infer_client_without_overriding_explicit_client(self):
        cases = {
            "CORREIOS - BD1000001": ("Claro", "Correios"),
            "BANCO DO BRASIL - BD1000001": ("Claro", "Banco do Brasil"),
            "CAIXA ECONOMICA - BD1000001": ("Claro", "Caixa Econômica Federal"),
            "CARREFOUR - BD1000001": ("Claro", "Carrefour"),
            "FUST - BD1000001": ("Vivo", "Fust"),
            "L2L - BD1000001": ("Vivo", "L2L"),
            "MC DONALDS - BD1000001": ("Vivo", "Arcos Dourados"),
            "ESCOLAS CONECTADAS - BD1000001": ("Algar", "Escolas Conectadas"),
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                result = LinkBusinessIdentityService.parse(name)
                self.assertEqual((result.contracting_client, result.business_project), expected)
                self.assertEqual(result.source, "CMDB_PROJECT_RULE")

    def test_explicit_client_wins_shared_project_and_diversos_never_infers(self):
        telmex = LinkBusinessIdentityService.parse("TELMEX - BRADESCO - BD1000001")
        telefonica = LinkBusinessIdentityService.parse("TELEFONICA BRASIL S.A. - BRADESCO - BD1000002")
        claro_diversos = LinkBusinessIdentityService.parse("CLARO - DIVERSOS - NESTLE - BD1000003")
        vivo_diversos = LinkBusinessIdentityService.parse("VIVO - DIVERSOS - BD1000004")
        unknown = LinkBusinessIdentityService.parse("DIVERSOS - BD1000005")
        self.assertEqual((telmex.contracting_client_raw, telmex.contracting_client, telmex.business_project), ("TELMEX", "Claro", "Bradesco"))
        self.assertEqual((telefonica.contracting_client, telefonica.business_project), ("Vivo", "Bradesco"))
        self.assertEqual((claro_diversos.contracting_client, claro_diversos.business_project), ("Claro", "Diversos"))
        self.assertEqual((vivo_diversos.contracting_client, vivo_diversos.business_project), ("Vivo", "Diversos"))
        self.assertEqual((unknown.contracting_client, unknown.business_project), ("", "Diversos"))

    def test_region_like_projects_are_not_canonicalized_without_a_rule(self):
        for raw in ("Claro.al", "Claro.mt", "Claro.pr"):
            with self.subTest(raw=raw):
                self.assertEqual(LinkBusinessIdentityService.parse(f"CLARO - {raw} - BD1000001").business_project, raw)

    def test_unstructured_address_name_remains_ambiguous(self):
        result = LinkBusinessIdentityService.parse("AEROPORTO DE MANAUS - AVENIDA TORQUATO TAPAJÓS - AM")
        self.assertEqual(result.contracting_client, "")
        self.assertEqual(result.business_project, "")
        self.assertEqual(result.business_account, "")
        self.assertEqual(result.confidence, "LOW")
