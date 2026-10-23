import secrets
import threading
from datetime import timedelta

from django.db import IntegrityError
from django.utils import timezone

from aplicativos.integracoes.models import IntegrationLease


LEASE_SECONDS = 180


class Lease:
    """Cross-process lease backed by the Arion database."""

    def __init__(self, key):
        self.key = key
        self.token = secrets.token_hex(24)

    def acquire(self):
        now = timezone.now()
        try:
            IntegrationLease.objects.get_or_create(key=self.key, defaults={"expires_at": now})
        except IntegrityError:
            pass
        return IntegrationLease.objects.filter(key=self.key, expires_at__lte=now).update(
            owner_token=self.token, started_at=now, heartbeat_at=now,
            expires_at=now + timedelta(seconds=LEASE_SECONDS),
        ) == 1

    def heartbeat(self):
        now = timezone.now()
        return IntegrationLease.objects.filter(key=self.key, owner_token=self.token).update(
            heartbeat_at=now, expires_at=now + timedelta(seconds=LEASE_SECONDS),
        ) == 1

    def release(self):
        IntegrationLease.objects.filter(key=self.key, owner_token=self.token).update(
            owner_token="", started_at=None, heartbeat_at=None, expires_at=timezone.now(),
        )

    def keep_alive(self):
        stop = threading.Event()
        thread = threading.Thread(target=self._heartbeat_loop, args=(stop,), daemon=True)
        thread.start()
        return stop, thread

    def _heartbeat_loop(self, stop):
        while not stop.wait(20):
            if not self.heartbeat():
                return
