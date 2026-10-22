from django.apps import AppConfig
from django.db.models.signals import post_migrate


class ConfiguracoesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'aplicativos.configuracoes'


    def ready(self):
        from . import signals
        from .access_control import after_migrate

        post_migrate.connect(after_migrate, sender=self, dispatch_uid="configuracoes.bootstrap_access_profiles")
