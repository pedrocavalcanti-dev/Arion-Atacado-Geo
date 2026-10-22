from django.core.management.base import BaseCommand

from aplicativos.configuracoes.access_control import bootstrap_access


class Command(BaseCommand):
    help = "Create/update the initial Arion access profiles and preserve access for existing users."

    def handle(self, *args, **options):
        bootstrap_access(assign_existing=True)
        self.stdout.write(self.style.SUCCESS("Perfis de acesso atualizados."))
