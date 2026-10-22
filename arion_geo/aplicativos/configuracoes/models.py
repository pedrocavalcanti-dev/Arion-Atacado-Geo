from django.conf import settings
from django.db import models


class UserPreference(models.Model):
    class Theme(models.TextChoices):
        DARK = "dark", "Escuro"
        LIGHT = "light", "Claro"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="preferences")
    theme = models.CharField(max_length=5, choices=Theme.choices, default=Theme.DARK)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Preferência do usuário"
        verbose_name_plural = "Preferências dos usuários"

    def __str__(self):
        return f"{self.user} · {self.get_theme_display()}"


class UserDataScope(models.Model):
    class Mode(models.TextChoices):
        ALL = "all", "Todos os dados"
        CUSTOM = "custom", "Personalizado"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="data_scope")
    mode = models.CharField(max_length=8, choices=Mode.choices, default=Mode.ALL)
    allowed_operators = models.ManyToManyField("base_links.Operadora", blank=True, related_name="scoped_users")
    allowed_projects = models.ManyToManyField("base_links.Projeto", blank=True, related_name="scoped_users")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "escopo de dados"
        verbose_name_plural = "escopos de dados"
        permissions = [
            ("view_dashboard", "Can view the executive dashboard"),
            ("view_cockpit", "Can view the analytics cockpit"),
            ("save_analytics_views", "Can save analytics views"),
            ("view_map", "Can view the operational map"),
            ("view_rankings", "Can view provider rankings"),
            ("view_base", "Can view the CMDB base"),
            ("import_cmdb", "Can import and update the CMDB"),
            ("export_base", "Can export CMDB data"),
            ("manage_users", "Can manage user accounts"),
            ("manage_groups", "Can manage access groups and permissions"),
            ("manage_data_scopes", "Can manage user data scopes"),
            ("view_audit_log", "Can view audit log"),
            ("view_integrations", "Can view configured integrations"),
            ("view_system_info", "Can view system information"),
            ("view_ari", "Can access the ARI I.A preview"),
        ]

    def __str__(self):
        return f"{self.user} · {self.get_mode_display()}"
