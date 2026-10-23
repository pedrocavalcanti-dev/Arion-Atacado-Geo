from datetime import timedelta
from io import StringIO

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


class IntegrationWorkerTests(TestCase):
    def setUp(self):
        self.command = Command(stdout=StringIO(), stderr=StringIO())

    def test_due_sync_updates_success_snapshot_and_cursor(self):
        state, _ = IntegrationSyncState.objects.get_or_create(key="otrs")
        now = timezone.now()
        called = []
        self.command._due("otrs_full", timedelta(minutes=30), now, lambda current: (called.append(True) or {"records": 7, "cursor": now}))
        state.refresh_from_db()
        self.assertEqual(called, [True])
        self.assertEqual(state.records_count, 7)
        self.assertEqual(state.change_cursor, now)
        self.assertEqual(state.last_full_success_at, state.last_success_at)

    def test_failed_sync_preserves_cursor_and_records_safe_failure(self):
        state, _ = IntegrationSyncState.objects.get_or_create(key="otrs", defaults={"change_cursor": timezone.now() - timedelta(hours=1)})
        cursor = state.change_cursor
        now = timezone.now()
        def fail(_state):
            raise RuntimeError("source unavailable")
        self.command._due("otrs_fast", timedelta(minutes=1), now, fail)
        state.refresh_from_db()
        self.assertEqual(state.change_cursor, cursor)
        self.assertIn("RuntimeError", state.last_error)
        self.assertIsNotNone(state.last_error_at)
