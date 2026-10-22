from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import AriAttachment


@receiver(post_delete, sender=AriAttachment, dispatch_uid="ari.delete_private_attachment_file")
def delete_private_attachment_file(sender, instance, **kwargs):
    if instance.file and instance.file.name:
        instance.file.delete(save=False)
