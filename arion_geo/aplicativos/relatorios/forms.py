from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import MONTH_CHOICES, PenaltyCompetence, PenaltyTreatmentOverride, PenaltyTreatmentRow
from .validators import report_file_extension_validator, validate_report_file_size
from .services.workbooks import FIELD_LABELS, REQUIRED_IMPORT_FIELDS


class CompetenceCreateForm(forms.ModelForm):
    original_file = forms.FileField(
        required=False,
        label="Arquivo original",
        validators=(report_file_extension_validator, validate_report_file_size),
        widget=forms.ClearableFileInput(attrs={"accept": ".xls,.xlsx", "data-local-file": ""}),
    )
    competence_month = forms.TypedChoiceField(
        coerce=int,
        choices=MONTH_CHOICES,
        label="Mês",
        widget=forms.Select(attrs={"class": "reports-select", "data-report-month": ""}),
    )
    competence_year = forms.TypedChoiceField(
        coerce=int,
        choices=(),
        label="Ano",
        widget=forms.Select(attrs={"class": "reports-select", "data-report-year": ""}),
    )

    class Meta:
        model = PenaltyCompetence
        fields = ("competence_month", "competence_year")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.duplicate_competence = None
        current_year = timezone.localdate().year
        self.fields["competence_month"].choices = MONTH_CHOICES
        self.fields["competence_year"].choices = tuple((year, str(year)) for year in range(max(2000, current_year - 10), min(2100, current_year + 1) + 1))
        self.fields["competence_month"].initial = timezone.localdate().month
        self.fields["competence_year"].initial = current_year

    def clean(self):
        cleaned_data = super().clean()
        month = cleaned_data.get("competence_month")
        year = cleaned_data.get("competence_year")
        if month and year:
            existing = PenaltyCompetence.objects.filter(
                report_type=PenaltyCompetence.ReportType.CLARO_PENALTIES,
                competence_month=month,
                competence_year=year,
            ).first()
            if existing:
                self.duplicate_competence = existing
                self.add_error("competence_month", ValidationError(
                    f"Já existe uma competência Claro Multas para {existing.period_label}.",
                    code="duplicate_period",
                ))
        return cleaned_data


class WorkbookSelectionForm(forms.Form):
    header_row = forms.IntegerField(
        min_value=1,
        max_value=30,
        label="Linha do cabeçalho",
        widget=forms.NumberInput(attrs={"class": "reports-input", "min": 1, "max": 30}),
    )

    def __init__(self, *args, sheets, headers, selected_sheet=None, header_row=1, initial_mapping=None, **kwargs):
        super().__init__(*args, **kwargs)
        sheet_choices = [(sheet["name"], sheet["name"]) for sheet in sheets]
        self.fields["sheet_name"] = forms.ChoiceField(
            choices=[("", "Selecione uma aba")] + sheet_choices,
            label="Aba do arquivo",
            initial=selected_sheet or "",
            widget=forms.Select(attrs={"class": "reports-select", "data-workbook-sheet": ""}),
        )
        self.fields["header_row"].initial = header_row or 1
        self.headers = list(headers)
        initial_mapping = initial_mapping or {}
        choices = [("", "Não mapear")] + [(field, label) for field, label in FIELD_LABELS.items()]
        for index, source_header in enumerate(self.headers):
            self.fields[f"column_{index}"] = forms.ChoiceField(
                choices=choices,
                required=False,
                label=source_header or f"Coluna {index + 1}",
                initial=initial_mapping.get(str(index), ""),
                widget=forms.Select(attrs={"class": "reports-select reports-select--mapping"}),
            )

    def clean(self):
        cleaned_data = super().clean()
        mapping = {}
        field_indexes = {}
        for index in range(len(self.headers)):
            field = cleaned_data.get(f"column_{index}")
            if not field:
                continue
            if field in field_indexes:
                self.add_error(f"column_{index}", "Este campo já está associado a outra coluna.")
                continue
            field_indexes[field] = index
            mapping[str(index)] = field
        if self.is_bound and not self.errors:
            if not REQUIRED_IMPORT_FIELDS.issubset(set(mapping.values())):
                raise ValidationError("Associe ao menos as colunas REC e Designação antes de importar.")
            cleaned_data["column_mapping"] = mapping
        return cleaned_data


class TreatmentEditForm(forms.ModelForm):
    version = forms.IntegerField(widget=forms.HiddenInput)
    validation_code = forms.CharField(required=False, label="Senha de validação", widget=forms.PasswordInput(render_value=False))
    validation_code_2 = forms.CharField(required=False, label="Senha de validação 02", widget=forms.PasswordInput(render_value=False))
    clear_validation_code = forms.BooleanField(required=False, label="Remover senha de validação")
    clear_validation_code_2 = forms.BooleanField(required=False, label="Remover senha de validação 02")

    class Meta:
        model = PenaltyTreatmentRow
        fields = ("arion_opening_at", "arion_fetec_at", "isp", "root_cause", "observation", "amount_not_charged", "amount_not_charged_justification", "status", "treatment_justification", "decision", "decision_reason", "procedence")
        labels = {
            "arion_opening_at": "Abertura ARION",
            "arion_fetec_at": "FETEC ARION",
            "isp": "ISP",
            "root_cause": "Causa raiz",
            "observation": "Observação",
            "amount_not_charged": "Valor não cobrado",
            "amount_not_charged_justification": "Justificativa do valor não cobrado",
            "status": "Status",
            "treatment_justification": "Justificativa da tratativa",
            "decision": "Decisão",
            "decision_reason": "Motivo da decisão",
            "procedence": "Procedência",
        }
        widgets = {
            "arion_opening_at": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "reports-input"}, format="%Y-%m-%dT%H:%M"),
            "arion_fetec_at": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "reports-input"}, format="%Y-%m-%dT%H:%M"),
            "isp": forms.TextInput(attrs={"class": "reports-input", "maxlength": 160}),
            "root_cause": forms.TextInput(attrs={"class": "reports-input", "maxlength": 240}),
            "observation": forms.Textarea(attrs={"class": "reports-input", "rows": 3}),
            "amount_not_charged": forms.NumberInput(attrs={"class": "reports-input", "min": "0", "step": "0.01"}),
            "amount_not_charged_justification": forms.TextInput(attrs={"class": "reports-input", "maxlength": 500}),
            "status": forms.Select(attrs={"class": "reports-select"}),
            "treatment_justification": forms.TextInput(attrs={"class": "reports-input", "maxlength": 500}),
            "decision": forms.Select(attrs={"class": "reports-select", "data-treatment-decision": ""}),
            "decision_reason": forms.TextInput(attrs={"class": "reports-input", "maxlength": 500}),
            "procedence": forms.Select(attrs={"class": "reports-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["version"].initial = self.instance.version
            if self.instance.isp and self.instance.isp.isdecimal():
                self.initial["isp"] = ""
                self.fields["isp"].help_text = f"ID interno CMDB {self.instance.isp}; o nome não foi resolvido. Informe um nome para substituir."
        self.fields["amount_not_charged"].required = False
        self.fields["root_cause"].widget.attrs["list"] = "reports-root-causes"

    def clean(self):
        data = super().clean()
        if self.instance.pk and self.instance.isp and self.instance.isp.isdecimal() and not data.get("isp", "").strip():
            data["isp"] = self.instance.isp
        amount = data.get("amount_not_charged")
        if amount is None:
            data["amount_not_charged"] = amount = 0
        if amount is not None and amount < 0:
            self.add_error("amount_not_charged", "O valor deve ser zero ou maior.")
        if amount not in (None, 0) and not data.get("amount_not_charged_justification", "").strip():
            self.add_error("amount_not_charged_justification", "Informe a justificativa para o valor não cobrado.")
        if data.get("decision") in (
            PenaltyTreatmentRow.Decision.DUE,
            PenaltyTreatmentRow.Decision.REDUCED,
            PenaltyTreatmentRow.Decision.INVALID,
        ) and not data.get("decision_reason", "").strip():
            self.add_error("decision_reason", "Registre a justificativa da decisão financeira.")
        date_fields_changed = self.instance.pk and any(
            data.get(field) != getattr(self.instance, field)
            for field in ("arion_opening_at", "arion_fetec_at")
        )
        if (date_fields_changed or (not self.instance.pk and (data.get("arion_opening_at") or data.get("arion_fetec_at")))) and not data.get("treatment_justification", "").strip():
            self.add_error("treatment_justification", "Informe a justificativa da tratativa.")
        if self.instance.pk and data.get("status") != self.instance.status and not data.get("treatment_justification", "").strip():
            self.add_error("treatment_justification", "Informe o motivo da alteração de status.")
        if data.get("validation_code") and data.get("clear_validation_code"):
            self.add_error("validation_code", "Informe um novo valor ou selecione remoção, não ambos.")
        if data.get("validation_code_2") and data.get("clear_validation_code_2"):
            self.add_error("validation_code_2", "Informe um novo valor ou selecione remoção, não ambos.")
        return data


class TreatmentPauseForm(forms.Form):
    version = forms.IntegerField(widget=forms.HiddenInput)
    kind = forms.ChoiceField(label="Tipo", choices=(("MINUTES", "Minutos"), ("INTERVAL", "Intervalo")), widget=forms.Select(attrs={"class": "reports-select"}))
    minutes = forms.IntegerField(label="Minutos", required=False, min_value=1, widget=forms.NumberInput(attrs={"class": "reports-input", "min": 1}))
    started_at = forms.DateTimeField(label="Início", required=False, input_formats=("%Y-%m-%dT%H:%M",), widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "reports-input"}, format="%Y-%m-%dT%H:%M"))
    ended_at = forms.DateTimeField(label="Fim", required=False, input_formats=("%Y-%m-%dT%H:%M",), widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "reports-input"}, format="%Y-%m-%dT%H:%M"))
    reason = forms.CharField(label="Motivo", max_length=300, widget=forms.TextInput(attrs={"class": "reports-input"}))
    evidence = forms.CharField(label="Evidência / observação", max_length=500, widget=forms.TextInput(attrs={"class": "reports-input"}))

    def clean(self):
        data = super().clean()
        if data.get("kind") == "MINUTES" and (not data.get("minutes") or data.get("started_at") or data.get("ended_at")):
            raise ValidationError("Informe somente os minutos para esta pausa.")
        if data.get("kind") == "INTERVAL" and (not data.get("started_at") or not data.get("ended_at") or data.get("ended_at") <= data.get("started_at") or data.get("minutes")):
            raise ValidationError("Informe um intervalo válido para a pausa.")
        return data


class TreatmentOverrideForm(forms.Form):
    version = forms.IntegerField(widget=forms.HiddenInput)
    field = forms.ChoiceField(label="Campo", choices=PenaltyTreatmentOverride.Field.choices)
    value = forms.DecimalField(label="Novo valor", max_digits=16, decimal_places=4, widget=forms.NumberInput(attrs={"class": "reports-input", "step": "any"}))
    justification = forms.CharField(label="Justificativa", max_length=500, widget=forms.TextInput(attrs={"class": "reports-input"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
