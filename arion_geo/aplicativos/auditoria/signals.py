from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from .services import AuditService


@receiver(user_logged_in)
def login_success(sender, request, user, **kwargs):
    AuditService.record(request=request, user=user, category="AUTHENTICATION", action="LOGIN_SUCCESS", description="Login realizado")


@receiver(user_logged_out)
def logout_event(sender, request, user, **kwargs):
    AuditService.record(request=request, user=user, category="AUTHENTICATION", action="LOGOUT", description="Sessão encerrada")


@receiver(user_login_failed)
def login_failed(sender, credentials, request, **kwargs):
    AuditService.record(request=request, category="AUTHENTICATION", action="LOGIN_FAILED", description="Tentativa de login recusada")
