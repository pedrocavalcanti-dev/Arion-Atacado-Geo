from datetime import timedelta
from io import StringIO
from types import SimpleNamespace

from django.db import OperationalError
from django.test import TestCase
from django.utils import timezone

from aplicativos.integracoes.management.commands.integration_worker import Command
from aplicativos.integracoes.models import IntegrationLease, IntegrationSyncState
from aplicativos.integracoes.services.sync_lock import Lease


class IntegrationLeaseTests(TestCase):
    def test_active_lease_skips_and_expired_lease_can_be_reclaimed(self):
        first = Lease("cmdb")
        second = Lease("cmdb")
        self.assertTrue(first.acquire())
        self.assertFalse(second.acquire())
        IntegrationLease.objects.filter(key="cmdb").update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertTrue(second.acquire())
        second.release()

    def test_sync_lease_heartbeat_retries_a_transient_sqlite_lock(self):
        class StopAfterTwoIntervals:
            calls = 0

            def wait(self, _seconds):
                self.calls += 1
                return self.calls > 2

        class TemporarilyLockedLease:
            calls = 0

            def heartbeat(self):
                self.calls += 1
                if self.calls == 1:
                    raise OperationalError("database is locked")
                return False

        lease = TemporarilyLockedLease()
        Lease._heartbeat_loop(lease, StopAfterTwoIntervals())
        self.assertEqual(lease.calls, 2)


class IntegrationWorkerTests(TestCase):
    def setUp(self):
        self.command = Command(stdout=StringIO(), stderr=StringIO())

    def test_due_sync_updates_success_without_overwriting_command_cursor(self):
        cursor = timezone.now() - timedelta(minutes=3)
        state, _ = IntegrationSyncState.objects.get_or_create(key="otrs", defaults={"change_cursor": cursor})
        now = timezone.now()
        called = []
        self.command._due("otrs_full", now, lambda current: (called.append(True) or {"records": 7, "cursor": now}))
        state.refresh_from_db()
        self.assertEqual(called, [True])
        self.assertEqual(state.records_count, 7)
        self.assertEqual(state.change_cursor, cursor)
        self.assertEqual(state.last_full_success_at, state.last_success_at)

    def test_worker_cadences_and_failed_run_retry(self):
        now = timezone.now()
        recent_success = SimpleNamespace(status="success", finished_at=now - timedelta(minutes=1), started_at=now - timedelta(minutes=1))
        recent_failure = SimpleNamespace(status="failed", finished_at=now - timedelta(minutes=1), started_at=now - timedelta(minutes=1))
        retry_due = SimpleNamespace(status="failed", finished_at=now - timedelta(minutes=3), started_at=now - timedelta(minutes=3))
        old_success = SimpleNamespace(status="success", finished_at=now - timedelta(minutes=31), started_at=now - timedelta(minutes=31))
        stale_running = SimpleNamespace(status="running", started_at=now - timedelta(minutes=4))
        self.assertFalse(self.command._run_due(recent_success, now - timedelta(hours=1), timedelta(minutes=2), now))
        self.assertFalse(self.command._run_due(recent_failure, None, timedelta(minutes=2), now))
        self.assertTrue(self.command._run_due(retry_due, None, timedelta(minutes=2), now))
        self.assertTrue(self.command._run_due(old_success, None, timedelta(minutes=30), now))
        self.assertTrue(self.command._run_due(stale_running, None, timedelta(minutes=30), now))
        self.assertTrue(self.command._run_due(None, None, timedelta(minutes=30), now))

    def test_heartbeat_retries_sqlite_database_locked(self):
        class StopAfterTwoIntervals:
            calls = 0

            def wait(self, _seconds):
                self.calls += 1
                return self.calls > 2

        class TemporarilyLockedLease:
            calls = 0

            def heartbeat(self):
                self.calls += 1
                if self.calls == 1:
                    raise OperationalError("database is locked")
                return False

        lease = TemporarilyLockedLease()
        self.command._heartbeat(lease, StopAfterTwoIntervals())
        self.assertEqual(lease.calls, 2)

    def test_failed_sync_preserves_cursor_and_records_safe_failure(self):
        state, _ = IntegrationSyncState.objects.get_or_create(key="otrs", defaults={"change_cursor": timezone.now() - timedelta(hours=1)})
        cursor = state.change_cursor
        now = timezone.now()
        def fail(_state):
            raise RuntimeError("source unavailable")
        self.command._due("otrs_fast", now, fail)
        state.refresh_from_db()
        self.assertEqual(state.change_cursor, cursor)
        self.assertIn("RuntimeError", state.last_error)
        self.assertIsNotNone(state.last_error_at)
