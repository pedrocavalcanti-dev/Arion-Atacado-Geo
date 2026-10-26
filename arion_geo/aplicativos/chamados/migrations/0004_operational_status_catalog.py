from django.db import migrations, models


LEGACY_STATUS_MAP = {
    "NEW": ("OPEN", "Novo", "Em Aberto"),
    "IN_ANALYSIS": ("OPEN", "Em análise", "Em Aberto"),
    "WAITING_PROVIDER": ("ISP_IN_PROGRESS", "Aguardando operadora", "Em atendimento pela ISP"),
    "WAITING_CUSTOMER": ("OPEN", "Aguardando cliente", "Em Aberto"),
    "MONITORING": ("OPEN", "Monitorando", "Em Aberto"),
    "FINISHED_INTERNAL": ("RESOLVED", "Finalizado no ARION", "Resolvido"),
}

CURRENT_STATUSES = {
    "OPEN", "RESOLVED", "ISP_IN_PROGRESS", "FINANCIAL_PENDING", "TECH_VISIT",
    "POST_SALES_ANALYSIS", "OWNERSHIP_CHANGE", "LINK_CANCELLATION",
    "WAITING_VALIDATION", "CGNAT", "TUNNELS", "MASS_OUTAGE",
}


def migrate_legacy_tracking_statuses(apps, schema_editor):
    Tracking = apps.get_model("chamados", "TicketTracking")
    Event = apps.get_model("chamados", "TicketTrackingEvent")
    database = schema_editor.connection.alias

    for tracking in Tracking.objects.using(database).all().iterator(chunk_size=500):
        old_status = tracking.internal_status
        if old_status in CURRENT_STATUSES:
            continue
        new_status, old_label, new_label = LEGACY_STATUS_MAP.get(
            old_status,
            ("OPEN", old_status or "Status anterior", "Em Aberto"),
        )
        tracking.internal_status = new_status
        tracking.revision += 1
        tracking.save(using=database, update_fields=("internal_status", "revision", "updated_at"))
        Event.objects.using(database).create(
            tracking_id=tracking.pk,
            event_type="FIELD_CHANGED",
            field_name="internal_status",
            old_value=old_label,
            new_value=new_label,
            actor_id=None,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("chamados", "0003_ticketqueueview"),
    ]

    operations = [
        migrations.RunPython(migrate_legacy_tracking_statuses, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="tickettracking",
            name="internal_status",
            field=models.CharField(
                choices=[
                    ("OPEN", "Em Aberto"),
                    ("RESOLVED", "Resolvido"),
                    ("ISP_IN_PROGRESS", "Em atendimento pela ISP"),
                    ("FINANCIAL_PENDING", "Pendente financeira"),
                    ("TECH_VISIT", "AG. Visita Técnica"),
                    ("POST_SALES_ANALYSIS", "Em análise pelo Pós-Vendas"),
                    ("OWNERSHIP_CHANGE", "Troca de titularidade"),
                    ("LINK_CANCELLATION", "Cancelamento do Link"),
                    ("WAITING_VALIDATION", "Aguardando validação"),
                    ("CGNAT", "CGNAT"),
                    ("TUNNELS", "Túneis"),
                    ("MASS_OUTAGE", "Massiva"),
                ],
                default="OPEN",
                max_length=24,
            ),
        ),
    ]
