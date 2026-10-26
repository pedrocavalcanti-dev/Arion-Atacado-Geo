from django.test import SimpleTestCase

from .services.closing_reason import ClosingReasonCanonicalizer


class ClosingReasonCanonicalizerTests(SimpleTestCase):
    def test_confirmed_massive_failure_aliases_share_key_and_label(self):
        for raw in ("FalhaMassiva", "Falha Massiva", "Defeito Massivo"):
            with self.subTest(raw=raw):
                self.assertEqual(ClosingReasonCanonicalizer.key(raw), "falha_massiva")
                self.assertEqual(ClosingReasonCanonicalizer.display(raw), "Falha Massiva")
        self.assertEqual(
            ClosingReasonCanonicalizer.raw_values("falha_massiva"),
            ("FalhaMassiva", "Falha Massiva", "Defeito Massivo"),
        )

    def test_catalog_labels_and_confirmed_technical_aliases_share_options(self):
        options = ClosingReasonCanonicalizer.options(("EquipamentoSubstituido", "Equipamento Substituído"))
        self.assertEqual(options, [{"value": "equipamento_substituido", "label": "Equipamento Substituído"}])

    def test_similar_unconfirmed_motives_remain_distinct(self):
        first = "Falha Lógica"
        second = "Falha Lógica na Operadora"
        self.assertNotEqual(ClosingReasonCanonicalizer.key(first), ClosingReasonCanonicalizer.key(second))
        self.assertNotEqual(ClosingReasonCanonicalizer.display(first), ClosingReasonCanonicalizer.display(second))

    def test_confirmed_catalog_transition_aliases_share_canonical_categories(self):
        aliases = {
            "equipamento_travado": (
                "Equipamento travado/reinicilizado", "EquipamentoTravado", "Equipamento Travado",
            ),
            "rompimento_fibra": (
                "Rompimento/manut Fibra", "RompimentoFibra", "Rompimento de Fibra",
            ),
            "chamado_cancelado": ("Cancelado", "ChamadoCancelado", "Chamado Cancelado"),
            "conexao_incorreta_cabo_interface": (
                "Conexão Incorreta - Cabeamento/porta", "ConexaoIncorreta",
                "Conexão Incorreta - Cabo/Interface",
            ),
        }
        for key, raws in aliases.items():
            with self.subTest(key=key):
                self.assertEqual({ClosingReasonCanonicalizer.key(raw) for raw in raws}, {key})
                self.assertEqual(len({ClosingReasonCanonicalizer.display(raw) for raw in raws}), 1)
                self.assertTrue(set(raws).issubset(ClosingReasonCanonicalizer.raw_values(key)))

    def test_canonical_options_are_unique_and_hide_technical_keys(self):
        raw_values = (
            "Defeito Massivo", "FalhaMassiva", "Falha Massiva",
            "Equipamento travado/reinicilizado", "EquipamentoTravado",
            "Rompimento/manut Fibra", "RompimentoFibra",
            "SemIntervencaoTecnica", "Sem Intervenção Técnica",
        )
        options = ClosingReasonCanonicalizer.options(raw_values)
        self.assertEqual(len(options), len({option["value"] for option in options}))
        self.assertEqual(len(options), len({option["label"].casefold() for option in options}))
        self.assertEqual(
            [option["label"] for option in options],
            sorted((option["label"] for option in options), key=str.casefold),
        )
        self.assertEqual(
            {option["value"]: option["label"] for option in options},
            {
                "falha_massiva": "Falha Massiva",
                "equipamento_travado": "Equipamento Travado",
                "rompimento_fibra": "Rompimento de Fibra",
                "sem_intervencao_tecnica": "Sem Intervenção Técnica",
            },
        )
