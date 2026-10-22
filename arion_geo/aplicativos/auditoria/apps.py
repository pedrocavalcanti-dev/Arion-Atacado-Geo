from django.apps import AppConfig


class AuditoriaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'aplicativos.auditoria'

    def ready(self):
        from . import signals  # noqa: F401

