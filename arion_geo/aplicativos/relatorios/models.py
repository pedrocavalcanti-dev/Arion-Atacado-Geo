from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .validators import (
    report_file_extension_validator,
    report_original_upload_path,
    validate_report_file_size,
)


MONTH_CHOICES = (
    (1, "Janeiro"), (2, "Fevereiro"), (3, "Março"), (4, "Abril"),
    (5, "Maio"), (6, "Junho"), (7, "Julho"), (8, "Agosto"),
    (9, "Setembro"), (10, "Outubro"), (11, "Novembro"), (12, "Dezembro"),
)


class PenaltyCompetence(models.Model):
    class ReportType(models.TextChoices):
        CLARO_PENALTIES = "CLARO_PENALTIES", "Claro Multas"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        IMPORTING = "IMPORTING", "Importando"
        IN_TREATMENT = "IN_TREATMENT", "Em tratamento"
        REVIEW = "REVIEW", "Em revisão"
        FINALIZED = "FINALIZED", "Finalizado"
        ERROR = "ERROR", "Erro"

    report_type = models.CharField(max_length=32, choices=ReportType.choices, default=ReportType.CLARO_PENALTIES)
    competence_year = models.PositiveSmallIntegerField(validators=(MinValueValidator(2000), MaxValueValidator(2100)))
    competence_month = models.PositiveSmallIntegerField(choices=MONTH_CHOICES, validators=(MinValueValidator(1), MaxValueValidator(12)))
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    original_filename = models.CharField(max_length=255, blank=True)
    original_file = models.FileField(
        upload_to=report_original_upload_path,
        blank=True,
        validators=(report_file_extension_validator, validate_report_file_size),
    )
    original_file_size = models.PositiveBigIntegerField(null=True, blank=True)
    original_file_sha256 = models.CharField(max_length=64, blank=True, default="", db_index=True)
    original_file_extension = models.CharField(max_length=4, blank=True)
    original_uploaded_at = models.DateTimeField(null=True, blank=True)
    original_uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="uploaded_penalty_sources")
    workbook_sheets = models.JSONField(default=list, blank=True)
    original_sheet_name = models.CharField(max_length=255, blank=True)
    header_row = models.PositiveSmallIntegerField(null=True, blank=True)
    source_headers = models.JSONField(default=list, blank=True)
    column_mapping = models.JSONField(default=dict, blank=True)
    source_total_rows = models.PositiveIntegerField(default=0)
    imported_row_count = models.PositiveIntegerField(default=0)
    imported_at = models.DateTimeField(null=True, blank=True)
    import_error = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_penalty_competences")
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="updated_penalty_competences")
    finalized_at = models.DateTimeField(null=True, blank=True)
    finalized_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="finalized_penalty_competences")
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    deleted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="deleted_penalty_competences")
    delete_reason = models.CharField(max_length=500, blank=True)
    calculation_rule_set = models.CharField(max_length=64, default="CLARO_LEGACY_2026_V1")
    sla_profile = models.CharField(max_length=16, choices=(("ASYMMETRIC", "Assimétrico"), ("SYMMETRIC", "Simétrico"), ("CUSTOM", "Personalizado")), default="ASYMMETRIC")

    class Meta:
        ordering = ("-competence_year", "-competence_month", "-created_at")
        verbose_name = "competência de penalidades"
        verbose_name_plural = "competências de penalidades"
        constraints = (
            models.UniqueConstraint(
                fields=("report_type", "competence_year", "competence_month"),
                name="uniq_report_competence_period",
            ),
            models.CheckConstraint(
                condition=models.Q(competence_month__gte=1, competence_month__lte=12),
                name="report_comp_month_range",
            ),
            models.CheckConstraint(
                condition=models.Q(competence_year__gte=2000, competence_year__lte=2100),
                name="report_comp_year_range",
            ),
        )
        permissions = (
            ("view_reports", "Can view the reports module"),
            ("edit_treatments", "Can edit ARION treatments"),
            ("override_treatments", "Can apply treatment calculation overrides"),
            ("finalize_treatments", "Can finalize treatment competences"),
            ("finalize_with_pending", "Can explicitly finalize with pending rows"),
            ("reopen_treatments", "Can reopen finalized treatment competences"),
            ("export_treatments", "Can export treatment workbooks"),
            ("delete_finalized_penaltycompetence", "Can archive finalized penalty competences"),
        )

    @property
    def period_label(self):
        return f"{self.get_competence_month_display()} {self.competence_year}"

    def __str__(self):
        return f"{self.get_report_type_display()} · {self.period_label}"


class PenaltySourceRow(models.Model):
    competence = models.ForeignKey(PenaltyCompetence, on_delete=models.CASCADE, related_name="source_rows")
    source_row_number = models.PositiveIntegerField()
    source_data = models.JSONField()
    canonical_data = models.JSONField(default=dict, blank=True)
    row_hash = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("source_row_number",)
        constraints = (
            models.UniqueConstraint(fields=("competence", "source_row_number"), name="uniq_penalty_source_row_number"),
        )

    def __str__(self):
        return f"{self.competence} · linha {self.source_row_number}"


class PenaltyTreatmentRow(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        IN_ANALYSIS = "IN_ANALYSIS", "Em análise"
        TREATED = "TREATED", "Tratado"
        REVIEW = "REVIEW", "Em revisão"
        APPROVED = "APPROVED", "Aprovado"

    class Origin(models.TextChoices):
        UNSPECIFIED = "", "Não informada"
        MANUAL = "MANUAL", "Manual"
        OTRS = "OTRS", "OTRS"
        CMDB = "CMDB", "CMDB"
        CALCULATED = "CALCULATED", "Calculado"
        IMPORTED = "IMPORTED", "Importado"
        OVERRIDE = "OVERRIDE", "Override"

    class Decision(models.TextChoices):
        PENDING = "PENDING", "Pendente de análise"
        DUE = "DUE", "Cobrança devida"
        REDUCED = "REDUCED", "Cobrança reduzida"
        INVALID = "INVALID", "Cobrança indevida"
        REVIEW = "REVIEW", "Revisar"

    class Procedence(models.TextChoices):
        UNSPECIFIED = "UNSPECIFIED", "Não informada"
        PROCEDENT = "PROCEDENT", "Procedente"
        IMPROCEDENT = "IMPROCEDENT", "Improcedente"

    class EvidenceStatus(models.TextChoices):
        NOT_CHECKED = "NOT_CHECKED", "Não verificado"
        FOUND = "FOUND", "Ticket localizado"
        NOT_FOUND = "NOT_FOUND", "Sem evidência OTRS"
        AMBIGUOUS = "AMBIGUOUS", "Identificador ambíguo"

    class ComparisonStatus(models.TextChoices):
        NO_DIFFERENCE = "SEM_DIFERENCA", "Sem diferença"
        REDUCTION = "REDUCAO", "Redução"
        INCREASE = "AUMENTO", "Aumento"
        NO_TREATMENT = "SEM_TRATATIVA", "Sem tratativa"

    source_row = models.OneToOneField(PenaltySourceRow, on_delete=models.CASCADE, related_name="treatment")
    ticket_identifier = models.CharField(max_length=80, blank=True, db_index=True)
    ticket = models.ForeignKey("integracoes.OTRSTicket", null=True, blank=True, on_delete=models.SET_NULL, related_name="penalty_treatments")
    evidence_status = models.CharField(max_length=16, choices=EvidenceStatus.choices, default=EvidenceStatus.NOT_CHECKED, db_index=True)
    field_origins = models.JSONField(default=dict, blank=True)
    source_values = models.JSONField(default=dict, blank=True)
    arion_values = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    arion_opening_at = models.DateTimeField(null=True, blank=True)
    arion_opening_origin = models.CharField(max_length=12, choices=Origin.choices, default=Origin.MANUAL)
    arion_fetec_at = models.DateTimeField(null=True, blank=True)
    arion_fetec_origin = models.CharField(max_length=12, choices=Origin.choices, default=Origin.MANUAL)
    isp = models.CharField(max_length=160, blank=True)
    root_cause = models.CharField(max_length=240, blank=True)
    observation = models.TextField(blank=True)
    validation_code_ciphertext = models.TextField(blank=True, editable=False)
    validation_code_2_ciphertext = models.TextField(blank=True, editable=False)
    tmp_gross_minutes = models.PositiveIntegerField(null=True, blank=True)
    pause_minutes = models.PositiveIntegerField(default=0)
    tmp_calculated_minutes = models.PositiveIntegerField(null=True, blank=True)
    ev_calculated = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    inter_calculated = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    inter_effective = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    unavailability_calculated = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    unavailability_effective = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    penalty_arion = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    penalty_effective = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    amount_charged = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    amount_due = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    amount_not_charged = models.DecimalField(max_digits=14, decimal_places=2, default=0, blank=True)
    amount_not_charged_justification = models.CharField(max_length=500, blank=True)
    amount_not_charged_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="adjusted_penalty_treatments")
    amount_not_charged_at = models.DateTimeField(null=True, blank=True)
    total_calculated_arion = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    total_arion = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    total_claro = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    difference = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    amount_contested = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    reduction_percent = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    comparison_status = models.CharField(max_length=20, choices=ComparisonStatus.choices, default=ComparisonStatus.NO_TREATMENT, db_index=True)
    calculation_state = models.CharField(max_length=24, default="UNCALCULATED", db_index=True)
    version = models.PositiveIntegerField(default=1)
    treatment_justification = models.CharField(max_length=500, blank=True)
    decision = models.CharField(max_length=12, choices=Decision.choices, default=Decision.PENDING, db_index=True)
    decision_reason = models.CharField(max_length=500, blank=True)
    procedence = models.CharField(max_length=16, choices=Procedence.choices, default=Procedence.UNSPECIFIED, db_index=True)
    procedence_origin = models.CharField(max_length=12, choices=Origin.choices, default=Origin.UNSPECIFIED, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("source_row__source_row_number",)

    def __str__(self):
        return f"Tratativa da linha {self.source_row.source_row_number}"

    @property
    def has_penalty(self):
        from .services.calculations import row_has_penalty
        return row_has_penalty(self.source_row.canonical_data or self.source_values)


class PenaltyTreatmentTicket(models.Model):
    class Source(models.TextChoices):
        AUTOMATIC = "AUTOMATIC", "Identificador Claro"
        MANUAL = "MANUAL", "Associação manual"
        LEGACY = "LEGACY", "Vínculo anterior"

    treatment = models.ForeignKey(PenaltyTreatmentRow, on_delete=models.CASCADE, related_name="ticket_relations")
    otrs_ticket = models.ForeignKey("integracoes.OTRSTicket", on_delete=models.PROTECT, related_name="penalty_treatment_relations")
    is_primary = models.BooleanField(default=False, db_index=True)
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.MANUAL)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="penalty_ticket_relations")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-is_primary", "created_at", "pk")
        constraints = (
            models.UniqueConstraint(fields=("treatment", "otrs_ticket"), name="uniq_penalty_treatment_ticket"),
        )
        indexes = (models.Index(fields=("treatment", "is_primary"), name="penalty_ticket_primary_idx"),)

    def __str__(self):
        return f"{self.treatment_id} · {self.otrs_ticket.ticket_number}"


class PenaltyTreatmentPause(models.Model):
    class Kind(models.TextChoices):
        MINUTES = "MINUTES", "Minutos"
        INTERVAL = "INTERVAL", "Intervalo"

    treatment = models.ForeignKey(PenaltyTreatmentRow, on_delete=models.CASCADE, related_name="pauses")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    minutes = models.PositiveIntegerField(null=True, blank=True)
    reason = models.CharField(max_length=300)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "pk")
        constraints = (
            models.CheckConstraint(condition=models.Q(minutes__isnull=True) | models.Q(minutes__gt=0), name="report_pause_positive_minutes"),
        )

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.kind == self.Kind.MINUTES and (not self.minutes or self.started_at or self.ended_at):
            raise ValidationError("Informe somente os minutos para este tipo de pausa.")
        if self.kind == self.Kind.INTERVAL and (not self.started_at or not self.ended_at or self.ended_at <= self.started_at or self.minutes):
            raise ValidationError("Informe um intervalo válido para a pausa.")

    @property
    def duration_minutes(self):
        if self.kind == self.Kind.MINUTES:
            return self.minutes or 0
        if self.started_at and self.ended_at:
            return max(0, int((self.ended_at - self.started_at).total_seconds() // 60))
        return 0


class PenaltyTreatmentOverride(models.Model):
    class Field(models.TextChoices):
        TMP = "tmp", "TMP ARION"
        EV = "ev", "EV ARION"
        INTER = "inter", "Inter ARION"
        UNAVAILABILITY = "unavailability", "Indisp ARION"
        PENALTY = "penalty", "Penal ARION"

    treatment = models.ForeignKey(PenaltyTreatmentRow, on_delete=models.CASCADE, related_name="overrides")
    field = models.CharField(max_length=24, choices=Field.choices)
    calculated_value = models.DecimalField(max_digits=16, decimal_places=4, null=True, blank=True)
    override_value = models.DecimalField(max_digits=16, decimal_places=4)
    justification = models.CharField(max_length=500)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_penalty_overrides")
    created_at = models.DateTimeField(auto_now_add=True)
    removed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="removed_penalty_overrides")
    removed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("field", "-created_at")
        indexes = (models.Index(fields=("treatment", "field", "removed_at"), name="report_override_active_idx"),)


class PenaltyFinancialChange(models.Model):
    treatment = models.ForeignKey(PenaltyTreatmentRow, on_delete=models.CASCADE, related_name="financial_changes")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="penalty_financial_changes")
    previous_total = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    new_total = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    reason = models.CharField(max_length=500)
    source = models.CharField(max_length=24, default="TREATMENT")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("created_at", "pk")
        indexes = (models.Index(fields=("treatment", "created_at"), name="report_fin_change_idx"),)
