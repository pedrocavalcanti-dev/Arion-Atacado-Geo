"""Dedicated persisted scheduler; run independently from HTTP workers."""
import threading
import time
from datetime import timedelta

from django.core.management import BaseCommand, call_command
from django.utils import timezone

from aplicativos.integracoes.models import IntegrationSyncState
from aplicativos.integracoes.services.sync_lock import Lease


class Command(BaseCommand):
    help = "Executa sincronizações CMDB/OTRS em processo dedicado."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Avalia os jobs uma vez e encerra.")
        parser.add_argument("--interval", type=int, default=5, help="Intervalo de verificação em segundos.")

    def handle(self, *args, **options):
        interval = max(1, min(options["interval"], 60))
        worker = Lease("worker")
        if not worker.acquire():
            self.stderr.write(self.style.ERROR("An integration_worker is already active."))
            return
        worker_stop = threading.Event()
        worker_heartbeat = threading.Thread(target=self._heartbeat, args=(worker, worker_stop), daemon=True)
        worker_heartbeat.start()
        self.stdout.write("Worker de integrações iniciado (OTRS 1 min / full 30 min; CMDB 10 min).")
        try:
            while True:
                if not worker.heartbeat():
                    self.stderr.write(self.style.ERROR("Worker lease lost; stopping to avoid duplicate scheduling."))
                    break
                now = timezone.now()
                self._due("cmdb", timedelta(minutes=10), now, self._cmdb)
                state, _ = IntegrationSyncState.objects.get_or_create(key="otrs")
                if state.change_cursor is None or state.last_full_success_at is None or state.last_full_success_at <= now - timedelta(minutes=30):
                    self._due("otrs_full", timedelta(minutes=30), now, self._otrs_full)
                else:
                    self._due("otrs_fast", timedelta(minutes=1), now, self._otrs_fast)
                if options["once"]:
                    break
                time.sleep(interval)
        except KeyboardInterrupt:
            self.stdout.write("Stopping integration_worker.")
        finally:
            worker_stop.set()
            worker_heartbeat.join(timeout=2)
            worker.release()

    def _due(self, key, cadence, now, callback, force=False):
        state, _ = IntegrationSyncState.objects.get_or_create(key="cmdb" if key == "cmdb" else "otrs")
        last = state.last_started_at if key == "cmdb" else (state.last_full_success_at or state.last_started_at if key == "otrs_full" else state.last_started_at)
        if key == "otrs_full" and state.last_full_success_at is None:
            cadence = timedelta(minutes=1)
        if not force and last and last > now - cadence:
            return
        lease = Lease("cmdb" if key == "cmdb" else "otrs")
        if not lease.acquire():
            self.stdout.write(f"{key}: SKIP (lease ativo).")
            return
        stop = threading.Event()
        heartbeat = threading.Thread(target=self._heartbeat, args=(lease, stop), daemon=True)
        heartbeat.start()
        start = timezone.now()
        state.last_started_at = start
        state.save(update_fields=("last_started_at", "updated_at"))
        try:
            self.stdout.write(f"{key}: iniciando.")
            details = callback(state)
            state.last_success_at = timezone.now()
            state.last_error_at = None
            state.last_error = ""
            state.last_duration_ms = int((timezone.now() - start).total_seconds() * 1000)
            state.records_count = details.get("records")
            if key == "otrs_full":
                state.last_full_success_at = state.last_success_at
                state.change_cursor = details.get("cursor") or state.last_success_at
            elif key == "otrs_fast":
                state.change_cursor = details.get("cursor") or state.change_cursor
            state.save()
            self.stdout.write(self.style.SUCCESS(f"{key}: concluído em {state.last_duration_ms} ms."))
        except Exception as exc:
            state.last_error_at = timezone.now()
            state.last_error = f"Falha segura ({type(exc).__name__})"
            state.last_duration_ms = int((timezone.now() - start).total_seconds() * 1000)
            state.save(update_fields=("last_error_at", "last_error", "last_duration_ms", "updated_at"))
            self.stderr.write(self.style.ERROR(f"{key}: falhou ({type(exc).__name__}); snapshot e cursor preservados."))
        finally:
            stop.set()
            heartbeat.join(timeout=2)
            lease.release()

    @staticmethod
    def _heartbeat(lease, stop):
        while not stop.wait(20):
            if not lease.heartbeat():
                return

    @staticmethod
    def _cmdb(_state):
        call_command("sincronizar_cmdb", "--apply", "--scheduler-lease", verbosity=0)
        from aplicativos.integracoes.models import CMDBLinkMirror
        return {"records": CMDBLinkMirror.objects.filter(is_present_in_source=True).count()}

    @staticmethod
    def _otrs_full(_state):
        call_command("sincronizar_otrs", "--apply", "--full", "--scheduler-lease", verbosity=0)
        from aplicativos.integracoes.models import OTRSTicket
        tickets = OTRSTicket.objects.filter(is_present_in_queue=True)
        return {"records": tickets.count(), "cursor": tickets.order_by("-source_changed_at").values_list("source_changed_at", flat=True).first()}

    @staticmethod
    def _otrs_fast(state):
        call_command("sincronizar_otrs", "--apply", "--fast", "--scheduler-lease", verbosity=0)
        from aplicativos.integracoes.models import OTRSTicket
        tickets = OTRSTicket.objects.filter(is_present_in_queue=True)
        return {"records": tickets.count(), "cursor": tickets.order_by("-source_changed_at").values_list("source_changed_at", flat=True).first()}

