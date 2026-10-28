"""Versioned, Decimal-only financial calculations for Claro penalty treatment."""

from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from aplicativos.relatorios.models import PenaltyTreatmentOverride, PenaltyTreatmentRow


RULESET_LEGACY = "CLARO_LEGACY_2026_V1"
RULESET_CONTRACT_ROUND_15 = "CONTRACT_ROUND_15"
CENT = Decimal("0.01")
THIRTY = Decimal("30")


def money(value):
    if value is None:
        return None
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def source_total_claro(source):
    values = [_decimal(source.get(key)) for key in ("interconnection_fine", "penalty_fine", "unavailability_fine")]
    return money(sum((value or Decimal("0") for value in values), Decimal("0")))


def row_has_penalty(source):
    return any((_decimal(source.get(key)) or Decimal("0")) > 0 for key in (
        "interconnection_fine", "penalty_fine", "unavailability_fine",
    ))


def _decimal(value):
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _active_overrides(treatment):
    return {
        item.field: item.override_value
        for item in treatment.overrides.filter(removed_at__isnull=True).order_by("created_at", "pk")
    }


def calculate_treatment(treatment, *, save=True):
    """Recalculate one row; missing inputs remain NULL rather than becoming zero."""
    competence = treatment.source_row.competence
    source = treatment.source_row.canonical_data or treatment.source_values or {}
    opening = treatment.arion_opening_at
    fetec = treatment.arion_fetec_at
    gross = None
    if opening and fetec:
        gross = max(0, int((fetec - opening).total_seconds() // 60))
    pauses = sum(pause.duration_minutes for pause in treatment.pauses.all())
    net = max(0, gross - pauses) if gross is not None else None
    ev = _calculate_ev(net, competence.calculation_rule_set)

    overrides = _active_overrides(treatment)
    effective_tmp = int(overrides[PenaltyTreatmentOverride.Field.TMP]) if PenaltyTreatmentOverride.Field.TMP in overrides else net
    effective_ev = overrides.get(PenaltyTreatmentOverride.Field.EV, _calculate_ev(effective_tmp, competence.calculation_rule_set))
    monthly = _decimal(source.get("monthly_value"))
    inter_calculated = money((Decimal(3) * monthly * ev) / Decimal(1440)) if monthly is not None and ev is not None else None
    inter_effective = money((Decimal(3) * monthly * effective_ev) / Decimal(1440)) if monthly is not None and effective_ev is not None else None
    profile = competence.sla_profile
    indisp_calculated = _calculate_indisp(monthly, net, profile)
    indisp_effective = _calculate_indisp(monthly, effective_tmp, profile)
    if PenaltyTreatmentOverride.Field.INTER in overrides:
        inter_effective = money(overrides[PenaltyTreatmentOverride.Field.INTER])
    if PenaltyTreatmentOverride.Field.UNAVAILABILITY in overrides:
        indisp_effective = money(overrides[PenaltyTreatmentOverride.Field.UNAVAILABILITY])
    penalty_claro = _decimal(source.get("penalty_fine")) or Decimal("0")
    penalty_effective = money(overrides[PenaltyTreatmentOverride.Field.PENALTY]) if PenaltyTreatmentOverride.Field.PENALTY in overrides else (Decimal("0.00") if penalty_claro <= 0 else None)
    penalty_calculated = Decimal("0.00") if penalty_claro <= 0 else None

    charged = money(inter_effective + indisp_effective + penalty_effective) if inter_effective is not None and indisp_effective is not None and penalty_effective is not None else None
    due = charged
    not_charged = treatment.amount_not_charged
    total_arion = money(due + not_charged) if due is not None and not_charged is not None else None
    total_calculated = money(inter_calculated + indisp_calculated + penalty_calculated) if inter_calculated is not None and indisp_calculated is not None and penalty_calculated is not None else None
    total_claro = source_total_claro(source)
    difference = money(total_claro - total_arion) if total_claro is not None and total_arion is not None else None
    contested = max(Decimal("0.00"), difference) if difference is not None else None
    reduction = (contested / total_claro * Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if contested is not None and total_claro and total_claro > 0 else None
    if difference is None:
        comparison_status = "SEM_TRATATIVA"
    elif difference == 0:
        comparison_status = "SEM_DIFERENCA"
    elif difference > 0:
        comparison_status = "REDUCAO"
    else:
        comparison_status = "AUMENTO"

    treatment.tmp_gross_minutes = gross
    treatment.pause_minutes = pauses
    treatment.tmp_calculated_minutes = net
    treatment.ev_calculated = ev
    treatment.inter_calculated = inter_calculated
    treatment.inter_effective = inter_effective
    treatment.unavailability_calculated = indisp_calculated
    treatment.unavailability_effective = indisp_effective
    treatment.penalty_arion = penalty_calculated  # No formula when Claro charged a penalty.
    treatment.penalty_effective = penalty_effective
    treatment.amount_charged = charged
    treatment.amount_due = due
    treatment.total_calculated_arion = total_calculated
    treatment.total_arion = total_arion
    treatment.total_claro = total_claro
    treatment.difference = difference
    treatment.amount_contested = contested
    treatment.reduction_percent = reduction
    treatment.comparison_status = comparison_status
    treatment.calculation_state = "CALCULATED" if total_arion is not None else "INCOMPLETE"
    if save:
        treatment.save(update_fields=(
            "tmp_gross_minutes", "pause_minutes", "tmp_calculated_minutes", "ev_calculated",
            "inter_calculated", "inter_effective", "unavailability_calculated", "unavailability_effective",
            "penalty_arion", "penalty_effective", "amount_charged", "amount_due", "total_calculated_arion", "total_arion", "total_claro", "difference",
            "amount_contested", "reduction_percent", "comparison_status", "calculation_state", "updated_at",
        ))
    return treatment


def _calculate_indisp(monthly, tmp_minutes, profile):
    rate = None
    if monthly is not None and tmp_minutes is not None and profile == "ASYMMETRIC":
        if tmp_minutes <= 1440:
            rate = Decimal("0")
        elif tmp_minutes <= 2880:
            rate = Decimal("0.05")
        elif tmp_minutes <= 4320:
            rate = Decimal("0.10")
        elif tmp_minutes <= 5760:
            rate = Decimal("0.15")
        else:
            rate = Decimal("0.20")
    elif monthly is not None and tmp_minutes is not None and profile == "SYMMETRIC":
        # The documented symmetric schedule has gaps; leave those intervals uncalculated.
        if 240 <= tmp_minutes <= 480:
            rate = Decimal("0.05")
        elif 540 <= tmp_minutes <= 720:
            rate = Decimal("0.10")
        elif 780 <= tmp_minutes <= 1440:
            rate = Decimal("0.15")
        elif 1500 <= tmp_minutes <= 43200:
            rate = Decimal("0.20")
        elif tmp_minutes < 240:
            rate = Decimal("0")
    return money(monthly * rate) if rate is not None else None


def effective_values(treatment):
    overrides = _active_overrides(treatment)
    tmp = overrides.get(PenaltyTreatmentOverride.Field.TMP, treatment.tmp_calculated_minutes)
    ev = overrides.get(PenaltyTreatmentOverride.Field.EV, _calculate_ev(tmp, treatment.source_row.competence.calculation_rule_set))
    return {
        "tmp": tmp,
        "ev": ev,
        "inter": treatment.inter_effective,
        "unavailability": treatment.unavailability_effective,
        "penalty": treatment.penalty_effective,
    }


def _calculate_ev(minutes, rule_set):
    if minutes is None:
        return None
    if rule_set == RULESET_LEGACY:
        return (Decimal(minutes) / THIRTY).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    if rule_set == RULESET_CONTRACT_ROUND_15:
        # Round half-up to 30-minute EV periods; an exact 15-minute fraction rounds up.
        return (Decimal(minutes) / THIRTY).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return None
