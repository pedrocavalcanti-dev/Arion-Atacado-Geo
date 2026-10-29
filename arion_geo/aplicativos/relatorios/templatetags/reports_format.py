from decimal import Decimal, ROUND_HALF_UP

from django import template
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime


register = template.Library()


def _br_number(value):
    text = str(value).strip().replace("R$", "").replace(" ", "")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    return f"{Decimal(text):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@register.filter
def br_currency(value):
    if value is None or value == "":
        return "—"
    try:
        return f"R$ {_br_number(value)}"
    except Exception:
        return "—"


@register.filter
def br_decimal(value):
    if value is None or value == "":
        return "—"
    try:
        result = Decimal(str(value)).normalize()
        text = format(result, "f")
        return text.replace(".", ",")
    except Exception:
        return "—"


@register.filter
def br_precision(value):
    """Render a Decimal with at most two places without changing stored values."""
    if value is None or value == "":
        return "—"
    try:
        rounded = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return br_decimal(rounded)
    except Exception:
        return "—"


@register.filter
def br_datetime(value, compact=False):
    if not value:
        return "—"
    try:
        if isinstance(value, str):
            value = parse_datetime(value) or parse_date(value)
        if not value:
            return "—"
        value = timezone.localtime(value) if timezone.is_aware(value) else value
        return value.strftime("%d/%m %H:%M" if compact else "%d/%m/%Y %H:%M")
    except (AttributeError, TypeError, ValueError):
        return "—"


@register.filter
def br_datetime_full(value):
    if not value:
        return "—"
    try:
        if isinstance(value, str):
            value = parse_datetime(value) or parse_date(value)
        if not value:
            return "—"
        value = timezone.localtime(value) if timezone.is_aware(value) else value
        return value.strftime("%d/%m/%Y %H:%M:%S")
    except (AttributeError, TypeError, ValueError):
        return "—"


@register.filter
def duration_label(value):
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        return "—"
    if minutes < 0:
        return "—"
    hours, remainder = divmod(minutes, 60)
    return f"{hours}h{remainder:02d}" if hours else f"{minutes} min"


@register.filter
def isp_display(value):
    text = str(value or "").strip()
    return "ISP não identificado" if not text or text.isdecimal() else text


@register.filter
def isp_internal_id(value):
    text = str(value or "").strip()
    return text if text.isdecimal() else ""


@register.filter
def datetime_local(value):
    if not value:
        return ""
    try:
        value = timezone.localtime(value) if timezone.is_aware(value) else value
        return value.strftime("%Y-%m-%dT%H:%M")
    except (AttributeError, TypeError, ValueError):
        return ""
