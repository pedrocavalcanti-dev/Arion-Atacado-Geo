from django.core.management.base import BaseCommand

from aplicativos.configuracoes.access_control import bootstrap_access


class Command(BaseCommand):
    help = "Create/update access profiles and default group data scopes without assigning users."

    def handle(self, *args, **options):
        bootstrap_access()
        self.stdout.write(self.style.SUCCESS("Perfis de acesso atualizados."))
