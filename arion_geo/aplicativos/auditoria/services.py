import re

from .models import AuditEvent


SENSITIVE_KEY_PARTS = (
    "password", "senha", "token", "secret", "cookie", "credential",
    "authorization", "sessionid", "apikey", "accesskey", "privatekey",
)


def sanitize_metadata(value):
    """Return JSON-safe metadata without credential-like keys, recursively."""
    if isinstance(value, dict):
        safe = {}
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).casefold())
            if any(part in normalized for part in SENSITIVE_KEY_PARTS):
                continue
            safe[str(key)] = sanitize_metadata(item)
        return safe
    if isinstance(value, (list, tuple, set)):
        return [sanitize_metadata(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


class AuditService:
    @staticmethod
    def record(*, request=None, user=None, category, action, description="", obj=None, metadata=None):
        safe_metadata = sanitize_metadata(metadata or {})
        remote = request.META.get("REMOTE_ADDR") if request else None
        agent = request.META.get("HTTP_USER_AGENT", "")[:500] if request else ""
        actor = user or getattr(request, "user", None)
        if not getattr(actor, "is_authenticated", False):
            actor = None
        return AuditEvent.objects.create(
            user=actor, category=category, action=action,
            description=description, object_type=obj.__class__.__name__ if obj else "",
            object_id=str(obj.pk) if obj and obj.pk else "", ip_address=remote,
            user_agent=agent, metadata=safe_metadata)
