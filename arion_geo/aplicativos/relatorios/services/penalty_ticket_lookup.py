"""Bounded, explicit, read-only lookup in the general OTRS database."""

from contextlib import nullcontext

from aplicativos.integracoes.models import Integration
from aplicativos.integracoes.services.otrs_sync import OTRSSyncService
from aplicativos.integracoes.clients.factory import configured_otrs_client


REMOTE_LOOKUP_ERROR = "Não foi possível consultar as evidências OTRS neste momento."
MAX_REMOTE_CANDIDATES = 500
MAX_LOOKUP_SPECS = 100
REMOTE_LOOKUP_LIMIT_ERROR = "A busca OTRS excedeu o limite seguro de candidatos. Confirme o ticket manualmente."


class LookupResults(list):
    def __init__(self, items=(), *, truncated=False):
        super().__init__(items)
        self.truncated = bool(truncated)


def _iso(value):
    return value.isoformat() if hasattr(value, "isoformat") else (str(value) if value not in (None, "") else None)


def _integration_client():
    integration = Integration.objects.filter(key=Integration.Key.OTRS, enabled=True).first()
    if integration is None:
        raise RuntimeError(REMOTE_LOOKUP_ERROR)
    return configured_otrs_client(integration)


def lookup_general_otrs(specs, *, client=None):
    """Search only candidate ticket numbers/prefixes and exact LP title tokens.

    The configured OTRSReadOnlyClient opens one read-only session and accepts
    only SELECT statements. The result is bounded and contains ticket metadata
    needed by Claro Multas, never articles, bodies, credentials, or attachments.
    """
    all_specs = [dict(item) for item in specs]
    specs_truncated = len(all_specs) > MAX_LOOKUP_SPECS
    specs = all_specs[:MAX_LOOKUP_SPECS]
    if not specs:
        return []
    client = client or _integration_client()
    session = getattr(client, "read_only_session", None)
    with session() if session else nullcontext(client):
        sync = OTRSSyncService(client)
        # General lookup needs only ticket metadata. Do not require the extra
        # tables used by the full queue synchronizer to be present or granted.
        schema_rows = client.get_all_columns()
        for row in schema_rows:
            table = str(row.get("TABLE_NAME", row.get("table_name", "")) or "")
            column = str(row.get("COLUMN_NAME", row.get("column_name", "")) or "")
            if table and column:
                sync.tables.add(table)
                sync.columns.setdefault(table.casefold(), set()).add(column)
        ticket_id = sync._column("ticket", "id", required=True)
        ticket_number = sync._column("ticket", "tn", required=True)
        title_column = sync._column("ticket", "title")

        selected = []
        fields = [("external_id", "id"), ("ticket_number", "tn"), ("title", "title"),
                  ("queue_external_id", "queue_id"), ("external_state_id", "ticket_state_id"),
                  ("responsible_user_id", "responsible_user_id"), ("source_created_at", "create_time"),
                  ("source_changed_at", "change_time")]
        for alias, name in fields:
            quoted = sync._column("ticket", name)
            if quoted:
                selected.append(f"{quoted} AS `{alias}`")

        exact_numbers = sorted({str(item.get("identifier") or "") for item in specs if item.get("identifier")})
        prefixes = sorted({str(item.get("prefix") or "") for item in specs if item.get("prefix")})
        lp_values = sorted({str(item.get("lp") or "").strip() for item in specs if item.get("lp")})
        rows_by_number = {}
        truncated = specs_truncated

        def fetch(conditions, params):
            nonlocal truncated
            remaining = MAX_REMOTE_CANDIDATES - len(rows_by_number)
            if not conditions:
                return
            if remaining <= 0:
                truncated = True
                return
            sql = (
                f"SELECT {', '.join(selected)} FROM {sync._table('ticket')} WHERE "
                f"({' OR '.join(conditions)}) ORDER BY {ticket_id} DESC LIMIT {remaining + 1}"
            )
            found_rows = client.execute_select(sql, tuple(params))
            if len(found_rows) > remaining:
                truncated = True
            for row in found_rows[:remaining]:
                number = str(row.get("ticket_number") or "")
                if number:
                    rows_by_number.setdefault(number, row)

        # Exact and rounded-PU candidates have priority over broad LP title hits
        # so unrelated recent tickets cannot crowd a known historical number.
        if exact_numbers:
            marks = ", ".join(["%s"] * len(exact_numbers))
            fetch([f"{ticket_number} IN ({marks})"], exact_numbers)
        if prefixes:
            prefix_conditions = [f"{ticket_number} LIKE %s" for _prefix in prefixes]
            fetch(prefix_conditions, [f"{prefix}%" for prefix in prefixes])
        if title_column and lp_values:
            lp_conditions = [f"{title_column} LIKE %s" for _lp in lp_values]
            fetch(lp_conditions, [f"%{lp}%" for lp in lp_values])
        rows = list(rows_by_number.values())

        queue_names, state_names = {}, {}
        queue_ids = sorted({row.get("queue_external_id") for row in rows if row.get("queue_external_id") is not None})
        state_ids = sorted({row.get("external_state_id") for row in rows if row.get("external_state_id") is not None})
        if queue_ids and sync._column("queue", "id") and sync._column("queue", "name"):
            marks = ", ".join(["%s"] * len(queue_ids))
            queue_rows = sync._select("queue", (("id", "id"), ("name", "name")),
                                      where=f"{sync._column('queue', 'id', required=True)} IN ({marks})",
                                      params=queue_ids)
            queue_names = {int(row["id"]): str(row.get("name") or "") for row in queue_rows}
        if state_ids and sync._column("ticket_state", "id") and sync._column("ticket_state", "name"):
            marks = ", ".join(["%s"] * len(state_ids))
            state_rows = sync._select("ticket_state", (("id", "id"), ("name", "name")),
                                      where=f"{sync._column('ticket_state', 'id', required=True)} IN ({marks})",
                                      params=state_ids)
            state_names = {int(row["id"]): str(row.get("name") or "") for row in state_rows}

    result = []
    for row in rows:
        result.append({
            "external_id": row.get("external_id"),
            "number": str(row.get("ticket_number") or ""),
            "title": str(row.get("title") or ""),
            "queue": queue_names.get(row.get("queue_external_id"), ""),
            "state": state_names.get(row.get("external_state_id"), ""),
            "responsible": row.get("responsible_user_id"),
            "created_at": _iso(row.get("source_created_at")),
            "changed_at": _iso(row.get("source_changed_at")),
            "closed_at": None,
            "source": "OTRS_GENERAL",
        })
    return LookupResults(result, truncated=truncated)
