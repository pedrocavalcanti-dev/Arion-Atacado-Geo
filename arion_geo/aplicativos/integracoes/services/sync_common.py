"""Small normalization helpers shared by the real-source mirror syncs."""
from datetime import datetime
import unicodedata

from django.utils import timezone
from django.utils.dateparse import parse_datetime


def clean(value, limit=None):
    if value is None or isinstance(value, (dict, list, tuple)):
        result = ""
    else:
        result = str(value).strip()
    return result[:limit] if limit else result


def normalized_name(value):
    text = unicodedata.normalize("NFKD", clean(value).casefold())
    return "".join(char for char in text if not unicodedata.combining(char))


def source_datetime(value):
    if value is None or value == "":
        return None
    parsed = value if isinstance(value, datetime) else parse_datetime(str(value).strip())
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def integer_or_none(value):
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None

