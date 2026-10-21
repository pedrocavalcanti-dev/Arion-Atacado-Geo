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
