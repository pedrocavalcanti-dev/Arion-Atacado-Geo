from django.db import IntegrityError, transaction

from aplicativos.relatorios.models import PenaltyCompetence


class CompetenceAlreadyExists(Exception):
    pass


@transaction.atomic
def create_draft_competence(*, user, month, year):
    if PenaltyCompetence.objects.filter(
        report_type=PenaltyCompetence.ReportType.CLARO_PENALTIES,
        competence_month=month,
        competence_year=year,
    ).exists():
        raise CompetenceAlreadyExists

    try:
        return PenaltyCompetence.objects.create(
            report_type=PenaltyCompetence.ReportType.CLARO_PENALTIES,
            competence_month=month,
            competence_year=year,
            status=PenaltyCompetence.Status.DRAFT,
            created_by=user,
            updated_by=user,
        )
    except IntegrityError as exc:
        raise CompetenceAlreadyExists from exc


def competence_counts(queryset):
    total = queryset.count()
    if not total:
        return {"in_treatment": None, "finalized": None, "total": 0, "latest": None}
    return {
        "in_treatment": queryset.filter(status__in=(PenaltyCompetence.Status.IN_TREATMENT, PenaltyCompetence.Status.REVIEW)).count(),
        "finalized": queryset.filter(status=PenaltyCompetence.Status.FINALIZED).count(),
        "total": total,
        "latest": queryset.first(),
    }
