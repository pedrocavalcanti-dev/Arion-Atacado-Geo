import uuid

from django.conf import settings
from django.db import models


class AriConversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ari_conversations")
    title = models.CharField(max_length=80, default="Nova conversa")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)
        indexes = [models.Index(fields=("user", "-updated_at"), name="ari_conv_user_updated_idx")]

    def __str__(self):
        return self.title


class AriMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "Usuário"
        ASSISTANT = "assistant", "ARI"

    conversation = models.ForeignKey(AriConversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=12, choices=Role.choices)
    content = models.TextField()
    message_type = models.CharField(max_length=24, default="text")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "pk")

    def __str__(self):
        return f"{self.get_role_display()} · {self.created_at:%Y-%m-%d %H:%M}"


class AriAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(AriConversation, on_delete=models.CASCADE, related_name="attachments")
    message = models.ForeignKey(AriMessage, on_delete=models.CASCADE, related_name="attachments")
    original_name = models.CharField(max_length=255)
    file = models.FileField(upload_to="ari/attachments/%Y/%m/")
    mime_type = models.CharField(max_length=120)
    size = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "pk")

    def __str__(self):
        return self.original_name


class AriArtifact(models.Model):
    class Type(models.TextChoices):
        REPORT_HTML = "report_html", "Relatório demonstrativo"
        DASHBOARD_HTML = "dashboard_html", "Dashboard demonstrativo"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(AriConversation, on_delete=models.CASCADE, related_name="artifacts")
    message = models.ForeignKey(AriMessage, on_delete=models.CASCADE, related_name="artifacts")
    artifact_type = models.CharField(max_length=24, choices=Type.choices)
    title = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "pk")

    def __str__(self):
        return self.title
