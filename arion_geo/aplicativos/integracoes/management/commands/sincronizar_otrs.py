from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count
from django.utils import timezone

from aplicativos.auditoria.services import AuditService
from aplicativos.integracoes.models import Integration, IntegrationRun, IntegrationSyncState, OTRSTicket, OTRSTicketConfigItem, OTRSStateMapping
from aplicativos.integracoes.services.errors import IntegrationError
from aplicativos.integracoes.services.otrs_sync import OTRSSyncService
from aplicativos.integracoes.views import _otrs_client
from aplicativos.integracoes.services.sync_lock import Lease


class Command(BaseCommand):
    help = "Sincroniza o espelho local da fila OTRS solicitada, em leitura somente no OTRS."

    def add_arguments(self, parser):
        parser.add_argument("--queue", default="NOC - ATACADO", help="Nome exato da fila OTRS.")
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--fast", action="store_true", help="Sincroniza somente tickets alterados desde o cursor, com janela de 2 minutos.")
        mode.add_argument("--full", action="store_true", help="Reconcilia a fila completa (padrão).")
        group = parser.add_mutually_exclusive_group()
        group.add_argument("--dry-run", action="store_true", dest="dry_run", help="Calcula as alterações sem gravar no espelho.")
        parser.add_argument("--scheduler-lease", action="store_true", help="Lease held by integration_worker.")
        group.add_argument("--apply", action="store_true", help="Aplica o snapshot local depois de uma leitura completa.")

    def handle(self, *args, **options):
        key = "otrs"
        lease = None if options.get("scheduler_lease") else Lease(key)
        if lease and not lease.acquire():
            raise CommandError("OTRS sync skipped: another run is active.")
        heartbeat = lease.keep_alive() if lease else None
        try:
            return self._execute(*args, **options)
        finally:
            if heartbeat:
                heartbeat[0].set()
                heartbeat[1].join(timeout=2)
            if lease:
                lease.release()

    def _execute(self, *args, **options):
        apply = bool(options.get("apply"))
        fast = bool(options.get("fast"))
        queue_name = options["queue"]
        state, _ = IntegrationSyncState.objects.get_or_create(key="otrs")
        if fast and state.change_cursor is None:
            raise CommandError("Cursor OTRS inexistente; execute primeiro uma reconciliação completa.")
        try:
            integration = Integration.objects.get(key=Integration.Key.OTRS)
            client = _otrs_client(integration)
        except Exception as exc:
            raise CommandError(f"Não foi possível preparar o client OTRS ({type(exc).__name__}).") from None
        if not client.database:
            try:
                system = {"information_schema", "mysql", "performance_schema", "sys"}
                applications = [name for name in client.list_databases() if name.casefold() not in system]
                if len(applications) != 1:
                    raise CommandError("Database OTRS não configurado e schema de aplicação não pôde ser determinado de forma única.")
                client.database = applications[0]
            except IntegrationError as exc:
                raise CommandError(f"Não foi possível descobrir o database OTRS ({type(exc).__name__}).") from None

        operation = IntegrationRun.Operation.OTRS_FAST_SYNC if fast else IntegrationRun.Operation.OTRS_FULL_SYNC
        run = IntegrationRun.objects.create(integration=integration, operation=operation, status=IntegrationRun.Status.RUNNING, message=("Fast " if fast else "Full ") + ("Apply " if apply else "Dry-run ") + queue_name[:210])
        state.last_started_at = run.started_at
        state.save(update_fields=("last_started_at", "updated_at"))
        AuditService.record(category="INTEGRATION", action="SYNC_STARTED", description="Sincronização OTRS iniciada", obj=run, module="Integrações", metadata={"source": "OTRS", "run_id": run.pk, "queue": queue_name, "mode": "apply" if apply else "dry-run"})
        service = OTRSSyncService(client, progress=self.stdout.write)
        try:
            with client.read_only_session():
                result = service.run(queue_name, apply=apply, changed_since=state.change_cursor if fast else None)
            run.status = IntegrationRun.Status.SUCCESS
            run.records_found = result["tickets"]["found"] + result["relations"]["found"]
            run.records_processed = result["tickets"]["processed"] + result["relations"]["processed"]
            run.records_created = result["tickets"]["created"] + result["relations"]["created"]
            run.records_updated = result["tickets"]["updated"] + result["relations"]["updated"]
            run.records_unchanged = result["tickets"]["unchanged"] + result["relations"]["unchanged"]
            run.records_stale = result["tickets"]["stale"] + result["relations"]["stale"]
            run.duration_ms = result["performance"]["duration_ms"]
            run.finished_at = timezone.now()
            run.message = self._summary(result, apply)
            run.save(update_fields=("status", "records_found", "records_processed", "records_created", "records_updated", "records_unchanged", "records_stale", "duration_ms", "finished_at", "message"))
            if apply:
                state.last_started_at = run.started_at
                state.last_success_at = run.finished_at
                state.last_error_at = None
                state.last_error = ""
                state.last_duration_ms = run.duration_ms
                state.records_count = OTRSTicket.objects.filter(is_present_in_queue=True).count()
                state.change_cursor = result.get("cursor") or state.change_cursor
                if not fast:
                    state.last_full_success_at = run.finished_at
                state.save()
            AuditService.record(category="INTEGRATION", action="SYNC_COMPLETED", description="Sincronização OTRS concluída", obj=run, module="Integrações", metadata={"source": "OTRS", "run_id": run.pk, "queue": queue_name, "counts": {"tickets": result["tickets"]["found"], "relations": result["relations"]["found"], "created": run.records_created, "updated": run.records_updated, "stale": run.records_stale}, "duration_ms": run.duration_ms})
        except Exception as exc:
            run.status = IntegrationRun.Status.FAILED
            run.records_failed = 1
            run.duration_ms = int((timezone.now() - run.started_at).total_seconds() * 1000)
            run.finished_at = timezone.now()
            run.message = f"Falha segura ({type(exc).__name__})"
            run.save(update_fields=("status", "records_failed", "duration_ms", "finished_at", "message"))
            state.last_error_at = timezone.now()
            state.last_error = f"Falha segura ({type(exc).__name__})"
            state.save(update_fields=("last_error_at", "last_error", "updated_at"))
            AuditService.record(category="INTEGRATION", action="SYNC_FAILED", description="Sincronização OTRS falhou", result="FAILURE", obj=run, module="Integrações", metadata={"source": "OTRS", "run_id": run.pk, "error_type": type(exc).__name__})
            raise CommandError(f"Sincronização OTRS cancelada ({type(exc).__name__}); snapshot local anterior preservado.") from None

        self.stdout.write(self.style.SUCCESS(f"OTRS {'APLICADO' if apply else 'DRY-RUN'} concluído: fila={result['queue']['name']} id={result['queue']['id']}."))
        self.stdout.write(f"Tickets: encontrados={result['tickets']['found']}; criados={result['tickets']['created']}; atualizados={result['tickets']['updated']}; inalterados={result['tickets']['unchanged']}; ausentes da fila={result['tickets']['stale']}.")
        self.stdout.write(f"Ticket-CI: {result['relations']['found']}; criadas={result['relations']['created']}; atualizadas={result['relations']['updated']}; ausentes={result['relations']['stale']}; ConfigItem sem Link local={result['relations']['unresolved_link']}.")
        relation_stats = result["relation_stats"]
        self.stdout.write(f"Cardinalidade: tickets com CI={relation_stats['tickets_with_ci']}; sem CI={relation_stats['tickets_without_ci']}; exatamente 1 CI={relation_stats['tickets_one_ci']}; múltiplos CIs={relation_stats['tickets_multiple_ci']}; ConfigItems únicos={relation_stats['unique_config_items']}; ConfigItems em múltiplos tickets={relation_stats['configitems_multiple_tickets']}.")
        self.stdout.write(f"CI-para-Link local: resolvidos={relation_stats['resolved_local_links']}; não resolvidos={relation_stats['unresolved_local_links']}.")
        self.stdout.write("Business status: " + "; ".join(f"{key}={value}" for key, value in result["business_status"].items()) + f"; total business-open={result['business_open']}.")
        self.stdout.write(f"Performance: {result['performance']['duration_ms']} ms; SELECT={result['performance']['select_queries']}; tickets={result['performance']['ticket_query_rows']}; batches de relação={result['performance']['relation_batches']}.")
        self.stdout.write(f"Warnings de estado ({len(result['warnings'])}): " + (" | ".join(result["warnings"]) if result["warnings"] else "nenhum"))
        if apply:
            self._print_local_proof()
        else:
            self.stdout.write("Prova e KPIs locais: execute com --apply para consultar exclusivamente o snapshot local.")

    @staticmethod
    def _summary(result, apply):
        return ("Apply" if apply else "Dry-run") + f"; queue={result['queue']['name']} id={result['queue']['id']}; tickets={result['tickets']['found']}; relations={result['relations']['found']}; open={result['business_open']}; warnings={len(result['warnings'])}"

    def _print_local_proof(self):
        current = OTRSTicket.objects.filter(is_present_in_queue=True)
        statuses = {row["business_status"]: row["total"] for row in current.values("business_status").annotate(total=Count("id"))}
        self.stdout.write(f"Snapshot local: tickets atuais na fila={current.count()}.")
        self.stdout.write("Status local: " + "; ".join(f"{status}={statuses.get(status, 0)}" for status in OTRSStateMapping.BusinessStatus.values))
        local_open = current.filter(is_business_open=True)
        related_open = OTRSTicketConfigItem.objects.filter(ticket__in=local_open, is_present_in_source=True)
        tickets_with_ci = related_open.values("ticket_id").distinct().count()
        tickets_with_link = related_open.exclude(cmdb_link__isnull=True).values("ticket_id").distinct().count()
        links_open = related_open.exclude(cmdb_link__isnull=True).values("cmdb_link_id").distinct().count()
        operators_open = related_open.exclude(cmdb_link__operator_id__isnull=True).values("cmdb_link__operator_id").distinct().count()
        self.stdout.write(f"Business-open={local_open.count()}; com CI={tickets_with_ci}; sem CI={max(0, local_open.count() - tickets_with_ci)}; com Link local={tickets_with_link}; links únicos={links_open}; operadoras={operators_open}.")
        unresolved = OTRSTicketConfigItem.objects.filter(ticket__in=current, is_present_in_source=True, cmdb_link__isnull=True).count()
        self.stdout.write(f"Relações Ticket-CI sem Link local={unresolved}.")
        resolved_state = current.filter(external_state_name__iexact="resolvido")
        self.stdout.write(f"resolvido: quantidade atual={resolved_state.count()}; business-open=NAO ({resolved_state.filter(is_business_open=True).count()} aberto[s]).")
        for ticket in current.filter(config_items__is_present_in_source=True, config_items__cmdb_link__operator__isnull=False).select_related().prefetch_related("config_items__cmdb_link__operator").distinct()[:5]:
            relation = ticket.config_items.filter(is_present_in_source=True, cmdb_link__isnull=False).select_related("cmdb_link", "cmdb_link__operator").first()
            if relation and relation.cmdb_link:
                link = relation.cmdb_link
                self.stdout.write(f"Prova local: ticket={ticket.ticket_number}; state={ticket.external_state_name}; business={ticket.business_status}; ConfigItemID={relation.config_item_id}; Number={link.source_number}; Link={link.name}; ISP={link.isp_raw}; Provedor={link.operator.name if link.operator else '(não resolvida)'}.")
                break

