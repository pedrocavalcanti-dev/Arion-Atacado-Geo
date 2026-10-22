from django.contrib.auth.decorators import permission_required


def access_required(codename):
    """Require a custom Django permission; superusers retain Django's bypass."""
    return permission_required(f"configuracoes.{codename}", raise_exception=True)
