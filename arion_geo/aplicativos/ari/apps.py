from django.apps import AppConfig


class AriConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "aplicativos.ari"
    verbose_name = "ARI I.A"

    def ready(self):
        from . import signals  # noqa: F401
