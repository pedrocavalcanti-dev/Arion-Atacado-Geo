from django.conf import settings
from django.db import models


class Provider(models.Model):
    name = models.CharField(max_length=160)
    normalized_name = models.CharField(max_length=180, unique=True)
    cmdb_config_item_id = models.CharField(max_length=40, blank=True, db_index=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "provedor"
        verbose_name_plural = "provedores"

    def __str__(self):
        return self.name


class Operadora(models.Model):
    name = models.CharField(max_length=100, unique=True)
    normalized_name = models.CharField(max_length=120, unique=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "operadora"
        verbose_name_plural = "operadoras"

    def __str__(self):
        return self.name


class Projeto(models.Model):
    name = models.CharField(max_length=140, unique=True)
    normalized_name = models.CharField(max_length=160, unique=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "projeto"
        verbose_name_plural = "projetos"

    def __str__(self):
        return self.name


class CMDBImport(models.Model):
    class Status(models.TextChoices):
        COMPLETED = "completed", "Concluída"
        COMPLETED_WITH_ERRORS = "completed_with_errors", "Concluída com erros"

    filename = models.CharField(max_length=255)
    file_sha256 = models.CharField(max_length=64, db_index=True)
    imported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cmdb_imports")
    created_at = models.DateTimeField(auto_now_add=True)
    total_rows = models.PositiveIntegerField(default=0)
    new_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    unchanged_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    unclassified_count = models.PositiveIntegerField(default=0)
    operational_count = models.PositiveIntegerField(default=0)
    canceled_count = models.PositiveIntegerField(default=0)
    maintenance_count = models.PositiveIntegerField(default=0)
    incident_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.COMPLETED)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "importação CMDB"
        verbose_name_plural = "importações CMDB"

    def __str__(self):
        return f"{self.filename} · {self.created_at:%d/%m/%Y %H:%M}"


class CMDBLink(models.Model):
    class ClassificationStatus(models.TextChoices):
        CLASSIFIED = "classified", "Classificado"
        UNCLASSIFIED = "unclassified", "Não classificado"

    config_item_id = models.CharField(max_length=40, unique=True, db_index=True)
    version = models.CharField(max_length=40, blank=True)
    source_class = models.CharField(max_length=120, blank=True)
    incident_state = models.CharField(max_length=80, blank=True, db_index=True)
    deployment_state = models.CharField(max_length=100, blank=True, db_index=True)
    name = models.CharField(max_length=300, blank=True)
    designation_arion = models.CharField(max_length=180, blank=True, db_index=True)
    cnpj_arion = models.CharField(max_length=40, blank=True)
    address = models.CharField(max_length=300, blank=True)
    city = models.CharField(max_length=120, blank=True, db_index=True)
    uf = models.CharField(max_length=2, blank=True, db_index=True)
    uf_raw = models.CharField(max_length=80, blank=True)
    client_raw = models.CharField(max_length=180, blank=True)
    circuit = models.CharField(max_length=180, blank=True)
    isp_raw = models.CharField(max_length=220, blank=True)
    provider = models.ForeignKey(Provider, null=True, blank=True, on_delete=models.SET_NULL, related_name="links")
    speed_raw = models.CharField(max_length=100, blank=True)
    range_ip = models.CharField(max_length=250, blank=True)
    link_type = models.CharField(max_length=120, blank=True)
    contract_number = models.CharField(max_length=140, blank=True)
    operator_designation = models.CharField(max_length=180, blank=True)
    client_identification = models.CharField(max_length=180, blank=True)
    business_hours = models.CharField(max_length=180, blank=True)
    notes = models.TextField(blank=True)
    source_created_at = models.DateTimeField(null=True, blank=True)
    source_payload = models.JSONField(default=dict, blank=True)
    operadora = models.ForeignKey(Operadora, null=True, blank=True, on_delete=models.SET_NULL, related_name="links")
    projeto = models.ForeignKey(Projeto, null=True, blank=True, on_delete=models.SET_NULL, related_name="links")
    classification_status = models.CharField(max_length=20, choices=ClassificationStatus.choices, default=ClassificationStatus.UNCLASSIFIED, db_index=True)
    synced_at = models.DateTimeField(null=True, blank=True)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    last_seen_import = models.ForeignKey(CMDBImport, null=True, blank=True, on_delete=models.SET_NULL, related_name="seen_links")
    is_present_in_latest_import = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("designation_arion", "config_item_id")
        indexes = [
            models.Index(fields=("uf", "deployment_state"), name="cmdb_uf_deploy_idx"),
            models.Index(fields=("incident_state", "classification_status"), name="cmdb_inc_class_idx"),
        ]
        verbose_name = "link CMDB"
        verbose_name_plural = "links CMDB"

    def __str__(self):
        return self.designation_arion or self.config_item_id


class CMDBLinkChange(models.Model):
    link = models.ForeignKey(CMDBLink, on_delete=models.CASCADE, related_name="changes")
    import_batch = models.ForeignKey(CMDBImport, on_delete=models.CASCADE, related_name="changes")
    field_name = models.CharField(max_length=60)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "alteração CMDB"
        verbose_name_plural = "alterações CMDB"

    def __str__(self):
        return f"{self.link} · {self.field_name}"
