from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models.signals import post_save
from django.dispatch import receiver

from .access_control import GROUP_ANALYST


@receiver(post_save, sender=get_user_model(), dispatch_uid="configuracoes.default_analyst_group")
def assign_default_access_profile(sender, instance, created, raw=False, **kwargs):
    if not created or raw or instance.is_superuser or not instance.is_active:
        return
    group = Group.objects.filter(name=GROUP_ANALYST).first()
    if group:
        instance.groups.add(group)
