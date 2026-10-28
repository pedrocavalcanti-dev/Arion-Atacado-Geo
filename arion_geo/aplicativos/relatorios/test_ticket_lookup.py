from contextlib import contextmanager
import unittest

from .services.penalty_ticket_lookup import lookup_general_otrs


class ReadOnlyLookupClient:
    def __init__(self):
        self.session_count = 0
        self.queries = []

    @contextmanager
    def read_only_session(self):
        self.session_count += 1
        yield self

    def get_all_columns(self):
        columns = {
            "ticket": ("id", "tn", "title", "queue_id", "ticket_state_id", "responsible_user_id", "create_time", "change_time"),
            "queue": ("id", "name"),
            "ticket_state": ("id", "name"),
        }
        return [
            {"TABLE_NAME": table, "COLUMN_NAME": column}
            for table, names in columns.items()
            for column in names
        ]

    def execute_select(self, sql, params=()):
        self.queries.append((sql, tuple(params)))
        if "FROM `ticket`" in sql:
            if "`tn` IN" in sql:
                return []
            if "`tn` LIKE" in sql:
                return [{
                    "external_id": 1001, "ticket_number": "2026100136000301",
                    "title": "BL30000096592 - CI: 603204", "queue_external_id": 4,
                    "external_state_id": 5, "responsible_user_id": 153,
                    "source_created_at": "2026-10-01 13:20:14", "source_changed_at": None,
                }]
            return []
        if "FROM `queue`" in sql:
            return [{"id": 4, "name": "Arquivo Geral"}]
        if "FROM `ticket_state`" in sql:
            return [{"id": 5, "name": "closed successful"}]
        return []


class GeneralOTRSLookupTests(unittest.TestCase):
    def test_lookup_uses_one_read_only_session_bounded_selects_and_safe_ticket_metadata(self):
        client = ReadOnlyLookupClient()
        tickets = lookup_general_otrs([{
            "identifier": "2026100136000300", "prefix": "202610013600030",
            "rec": "603204", "lp": "BL30000096592",
        }], client=client)

        self.assertEqual(client.session_count, 1)
        self.assertEqual(len(tickets), 1)
        self.assertEqual(tickets[0]["number"], "2026100136000301")
        self.assertEqual(tickets[0]["queue"], "Arquivo Geral")
        self.assertEqual(tickets[0]["state"], "closed successful")
        ticket_queries = [(sql, params) for sql, params in client.queries if "FROM `ticket`" in sql]
        self.assertGreaterEqual(len(ticket_queries), 2)
        for sql, _params in client.queries:
            self.assertTrue(sql.lstrip().upper().startswith("SELECT "))
            self.assertNotRegex(sql, r"(?i)\b(INSERT|UPDATE|DELETE|REPLACE|DROP|ALTER)\b")
            self.assertNotIn(";", sql)
        self.assertIn("2026100136000300", ticket_queries[0][1])
        self.assertEqual(ticket_queries[0][1], ("2026100136000300",))
        self.assertIn("202610013600030%", ticket_queries[1][1])
        self.assertTrue(all("LIMIT" in sql.upper() for sql, _params in ticket_queries))

    def test_no_specs_performs_no_remote_queries(self):
        client = ReadOnlyLookupClient()
        self.assertEqual(lookup_general_otrs([], client=client), [])
        self.assertEqual(client.session_count, 0)
        self.assertEqual(client.queries, [])
