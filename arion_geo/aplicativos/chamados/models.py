from django.conf import settings
from django.db import models


class TicketTracking(models.Model):
    """ARION-only follow-up, keyed by the stable OTRS external ticket ID."""

    class InternalStatus(models.TextChoices):
        OPEN = "OPEN", "Em Aberto"
        RESOLVED = "RESOLVED", "Resolvido"
        ISP_IN_PROGRESS = "ISP_IN_PROGRESS", "Em atendimento pela ISP"
        FINANCIAL_PENDING = "FINANCIAL_PENDING", "Pendente financeira"
        TECH_VISIT = "TECH_VISIT", "AG. Visita Técnica"
        POST_SALES_ANALYSIS = "POST_SALES_ANALYSIS", "Em análise pelo Pós-Vendas"
        OWNERSHIP_CHANGE = "OWNERSHIP_CHANGE", "Troca de titularidade"
        LINK_CANCELLATION = "LINK_CANCELLATION", "Cancelamento do Link"
        WAITING_VALIDATION = "WAITING_VALIDATION", "Aguardando validação"
        CGNAT = "CGNAT", "CGNAT"
        TUNNELS = "TUNNELS", "Túneis"
        MASS_OUTAGE = "MASS_OUTAGE", "Massiva"

    class InternalPriority(models.TextChoices):
        LOW = "LOW", "Baixa"
        NORMAL = "NORMAL", "Normal"
        HIGH = "HIGH", "Alta"
        CRITICAL = "CRITICAL", "Crítica"

    ticket_external_id = models.PositiveBigIntegerField(unique=True)
    internal_status = models.CharField(
        max_length=24, choices=InternalStatus.choices, default=InternalStatus.OPEN,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="operational_ticket_assignments",
    )
    internal_priority = models.CharField(max_length=12, choices=InternalPriority.choices, blank=True)
    next_action_at = models.DateTimeField(null=True, blank=True)
    revision = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="operational_ticket_tracking_updates",
    )

    class Meta:
        ordering = ("-updated_at", "ticket_external_id")
        indexes = [
            models.Index(fields=("internal_status",), name="tracking_status_idx"),
            models.Index(fields=("assigned_to",), name="tracking_assignee_idx"),
            models.Index(fields=("updated_at",), name="tracking_updated_idx"),
            models.Index(fields=("next_action_at",), name="tracking_next_action_idx"),
        ]
        verbose_name = "acompanhamento local de chamado"
        verbose_name_plural = "acompanhamentos locais de chamados"

    def __str__(self):
        return f"Acompanhamento ARION · {self.ticket_external_id}"


class TicketTrackingNote(models.Model):
    tracking = models.ForeignKey(TicketTracking, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="operational_ticket_notes",
    )
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        indexes = [models.Index(fields=("tracking", "created_at"), name="tracking_note_date_idx")]
        verbose_name = "nota interna ARION"
        verbose_name_plural = "notas internas ARION"

    def __str__(self):
        return f"Nota · {self.tracking.ticket_external_id} · {self.created_at:%Y-%m-%d %H:%M}"


class TicketTrackingEvent(models.Model):
    class EventType(models.TextChoices):
        FIELD_CHANGED = "FIELD_CHANGED", "Campo alterado"
        NOTE_ADDED = "NOTE_ADDED", "Nota adicionada"

    tracking = models.ForeignKey(TicketTracking, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    field_name = models.CharField(max_length=40, blank=True)
    old_value = models.CharField(max_length=240, blank=True)
    new_value = models.CharField(max_length=240, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="operational_ticket_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        indexes = [models.Index(fields=("tracking", "created_at"), name="tracking_event_date_idx")]
        verbose_name = "evento de acompanhamento ARION"
        verbose_name_plural = "eventos de acompanhamento ARION"

    def __str__(self):
        return f"{self.get_event_type_display()} · {self.tracking.ticket_external_id}"


class TicketQueueView(models.Model):
    """A user's private, validated set of operational queue filters."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_ticket_queue_views",
    )
    name = models.CharField(max_length=80)
    filters = models.JSONField(default=dict)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-is_default", "name", "pk")
        constraints = [
            models.UniqueConstraint(fields=("user", "name"), name="uniq_ticket_queue_view_name"),
        ]
        indexes = [models.Index(fields=("user", "is_default"), name="ticket_view_default_idx")]
        verbose_name = "fila salva de chamados"
        verbose_name_plural = "filas salvas de chamados"

    def __str__(self):
        return f"{self.name} · {self.user}"
