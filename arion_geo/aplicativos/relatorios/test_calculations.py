from datetime import datetime, timedelta, timezone as datetime_timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.test import TestCase
from django.utils import timezone

from .models import (
    PenaltyCompetence,
    PenaltySourceRow,
    PenaltyTreatmentOverride,
    PenaltyTreatmentPause,
    PenaltyTreatmentRow,
)
from .services.calculations import RULESET_CONTRACT_ROUND_15, calculate_treatment, effective_values


class PenaltyCalculationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="reports-calculator", password="password")
        self.competence = PenaltyCompetence.objects.create(competence_year=2026, competence_month=9)
        self.source = PenaltySourceRow.objects.create(
            competence=self.competence,
            source_row_number=2,
            source_data=[],
            canonical_data={
                "monthly_value": "2880.00",
                "interconnection_fine": "100.00",
                "penalty_fine": "20.00",
                "unavailability_fine": "30.00",
            },
            row_hash="f" * 64,
        )
        self.treatment = PenaltyTreatmentRow.objects.create(source_row=self.source, source_values=self.source.canonical_data)

    def set_interval(self, minutes):
        self.treatment.arion_opening_at = datetime(2026, 9, 1, tzinfo=datetime_timezone.utc)
        self.treatment.arion_fetec_at = self.treatment.arion_opening_at + timedelta(minutes=minutes)
        self.treatment.amount_not_charged = Decimal("0.00")
        self.treatment.save()

    def test_tmp_pause_ev_and_financial_totals(self):
        self.treatment.arion_opening_at = datetime(2026, 9, 1, 8, tzinfo=datetime_timezone.utc)
        self.treatment.arion_fetec_at = datetime(2026, 9, 1, 10, tzinfo=datetime_timezone.utc)
        self.treatment.amount_not_charged = Decimal("0.00")
        self.treatment.save()
        PenaltyTreatmentPause.objects.create(
            treatment=self.treatment, kind="MINUTES", minutes=30,
            reason="Aguardando cliente", created_by=self.user,
        )
        PenaltyTreatmentOverride.objects.create(
            treatment=self.treatment, field=PenaltyTreatmentOverride.Field.PENALTY,
            calculated_value=None, override_value=Decimal("0.00"),
            justification="Sem fórmula oficial de Penal ARION; valor validado manualmente.", created_by=self.user,
        )
        calculate_treatment(self.treatment)
        self.treatment.refresh_from_db()
        self.assertEqual(self.treatment.tmp_gross_minutes, 120)
        self.assertEqual(self.treatment.pause_minutes, 30)
        self.assertEqual(self.treatment.tmp_calculated_minutes, 90)
        self.assertEqual(self.treatment.ev_calculated, Decimal("3"))
        self.assertEqual(self.treatment.inter_calculated, Decimal("18.00"))
        self.assertEqual(self.treatment.unavailability_calculated, Decimal("0.00"))
        self.assertIsNone(self.treatment.total_calculated_arion)  # Penal Claro is positive; no ARION rule exists.
        self.assertIsNone(self.treatment.penalty_arion)
        self.assertEqual(self.treatment.penalty_effective, Decimal("0.00"))
        self.assertEqual(self.treatment.amount_charged, Decimal("18.00"))
        self.assertEqual(self.treatment.amount_due, Decimal("18.00"))
        self.assertEqual(self.treatment.total_claro, Decimal("150.00"))
        self.assertEqual(self.treatment.total_arion, Decimal("18.00"))
        self.assertEqual(self.treatment.difference, Decimal("132.00"))
        self.assertEqual(self.treatment.comparison_status, "REDUCAO")

    def test_legacy_decimal_ev_and_indisp_boundaries(self):
        expected = {
            1440: Decimal("0.00"), 1441: Decimal("144.00"),
            2880: Decimal("144.00"), 2881: Decimal("288.00"),
            4320: Decimal("288.00"), 4321: Decimal("432.00"),
            5760: Decimal("432.00"), 5761: Decimal("576.00"),
        }
        for minutes, fine in expected.items():
            with self.subTest(minutes=minutes):
                self.set_interval(minutes)
                calculate_treatment(self.treatment)
                self.treatment.refresh_from_db()
                self.assertEqual(self.treatment.unavailability_calculated, fine)
                self.assertEqual(self.treatment.ev_calculated, (Decimal(minutes) / Decimal(30)).quantize(Decimal("0.0001")))
        self.set_interval(75)
        calculate_treatment(self.treatment)
        self.treatment.refresh_from_db()
        self.assertEqual(self.treatment.ev_calculated, Decimal("2.5"))

    def test_interval_pause_and_multiple_pauses_reduce_tmp(self):
        self.set_interval(240)
        PenaltyTreatmentPause.objects.create(
            treatment=self.treatment, kind="INTERVAL",
            started_at=datetime(2026, 9, 1, 9, tzinfo=datetime_timezone.utc),
            ended_at=datetime(2026, 9, 1, 10, tzinfo=datetime_timezone.utc),
            reason="Aguardando terceiro",
        )
        PenaltyTreatmentPause.objects.create(
            treatment=self.treatment, kind="MINUTES", minutes=30, reason="Pausa adicional",
        )
        calculate_treatment(self.treatment)
        self.treatment.refresh_from_db()
        self.assertEqual(self.treatment.pause_minutes, 90)
        self.assertEqual(self.treatment.tmp_calculated_minutes, 150)

    def test_override_preserves_calculated_and_changes_effective_value(self):
        self.set_interval(300)
        calculate_treatment(self.treatment)
        calculated = self.treatment.ev_calculated
        override = PenaltyTreatmentOverride.objects.create(
            treatment=self.treatment, field="ev", calculated_value=calculated,
            override_value=Decimal("0"), justification="Evidência operacional revisada", created_by=self.user,
        )
        calculate_treatment(self.treatment)
        self.treatment.refresh_from_db()
        self.assertEqual(self.treatment.ev_calculated, Decimal("10"))
        self.assertEqual(effective_values(self.treatment)["ev"], Decimal("0"))
        self.assertEqual(self.treatment.inter_calculated, Decimal("60.00"))
        self.assertEqual(self.treatment.inter_effective, Decimal("0.00"))
        override.removed_at = datetime.now(datetime_timezone.utc)
        override.save(update_fields=("removed_at",))
        calculate_treatment(self.treatment)
        self.assertEqual(effective_values(self.treatment)["ev"], Decimal("10"))

    def test_null_inputs_are_distinct_from_zero_values_and_penalty_is_not_invented(self):
        calculate_treatment(self.treatment)
        self.treatment.refresh_from_db()
        self.assertIsNone(self.treatment.tmp_calculated_minutes)
        self.assertIsNone(self.treatment.total_arion)
        self.assertIsNone(self.treatment.penalty_arion)
        self.assertEqual(self.treatment.pause_minutes, 0)
        self.set_interval(0)
        calculate_treatment(self.treatment)
        self.treatment.refresh_from_db()
        self.assertEqual(self.treatment.tmp_calculated_minutes, 0)
        self.assertEqual(self.treatment.unavailability_calculated, Decimal("0.00"))

    def test_contract_round_15_is_available_without_changing_the_legacy_default(self):
        self.competence.calculation_rule_set = RULESET_CONTRACT_ROUND_15
        self.competence.save(update_fields=("calculation_rule_set",))
        self.set_interval(75)
        calculate_treatment(self.treatment)
        self.treatment.refresh_from_db()
        self.assertEqual(self.treatment.ev_calculated, Decimal("3"))

    def test_symmetric_profile_is_explicit_and_gap_stays_uncalculated(self):
        self.competence.sla_profile = "SYMMETRIC"
        self.competence.save(update_fields=("sla_profile",))
        self.set_interval(300)
        calculate_treatment(self.treatment)
        self.treatment.refresh_from_db()
        self.assertEqual(self.treatment.unavailability_calculated, Decimal("144.00"))
        self.set_interval(500)
        calculate_treatment(self.treatment)
        self.assertIsNone(self.treatment.unavailability_calculated)

    def test_pending_eligible_competence_cannot_be_finalized_even_with_legacy_override_permission(self):
        self.competence.imported_at = timezone.now()
        self.competence.save(update_fields=("imported_at",))
        permission = Permission.objects.get(codename="finalize_treatments", content_type__app_label="relatorios")
        self.user.user_permissions.add(permission)
        self.client.force_login(self.user)
        url = reverse("relatorios:competence-finalize", args=(self.competence.pk,))
        self.client.post(url)
        self.competence.refresh_from_db()
        self.assertNotEqual(self.competence.status, PenaltyCompetence.Status.FINALIZED)

        override_permission = Permission.objects.get(codename="finalize_with_pending", content_type__app_label="relatorios")
        self.user.user_permissions.add(override_permission)
        self.client.post(url)
        self.competence.refresh_from_db()
        self.assertNotEqual(self.competence.status, PenaltyCompetence.Status.FINALIZED)
        self.client.post(url, {"confirm_pending": "1"})
        self.competence.refresh_from_db()
        self.assertNotEqual(self.competence.status, PenaltyCompetence.Status.FINALIZED)

    def test_row_edit_endpoint_saves_with_version_and_rejects_stale_form(self):
        permission = Permission.objects.get(codename="edit_treatments", content_type__app_label="relatorios")
        self.user.user_permissions.add(permission)
        self.client.force_login(self.user)
        url = reverse("relatorios:treatment-edit", args=(self.treatment.pk,))
        data = {
            "version": "1", "arion_opening_at": "2026-09-01T08:00",
            "arion_fetec_at": "2026-09-01T10:00", "isp": "ISP Exemplo",
            "root_cause": "Falha de energia", "observation": "Análise registrada",
            "amount_not_charged": "0", "amount_not_charged_justification": "",
            "status": "IN_ANALYSIS", "treatment_justification": "Chamado conferido",
            "decision": "PENDING", "decision_reason": "",
            "procedence": "UNSPECIFIED",
            "validation_code": "", "validation_code_2": "",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.treatment.refresh_from_db()
        self.assertEqual(self.treatment.version, 2)
        self.assertEqual(self.treatment.tmp_calculated_minutes, 120)
        self.assertEqual(self.treatment.status, PenaltyTreatmentRow.Status.IN_ANALYSIS)
        self.assertFalse(self.treatment.amount_not_charged_at)
        self.assertIsNone(self.treatment.amount_not_charged_by)

        stale = self.client.post(url, {**data, "status": "TREATED"})
        self.assertEqual(stale.status_code, 200)
        self.treatment.refresh_from_db()
        self.assertEqual(self.treatment.status, PenaltyTreatmentRow.Status.IN_ANALYSIS)
