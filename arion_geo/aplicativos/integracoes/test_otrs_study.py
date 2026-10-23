import json
from unittest import TestCase

from aplicativos.integracoes.clients.otrs import OTRSReadOnlyClient
from aplicativos.integracoes.services.errors import OTRSDatabaseError
from aplicativos.integracoes.services.otrs_study import OTRSStudyService


def schema_fixture():
    tables = [
        ("queue", "BASE TABLE", 4), ("ticket", "BASE TABLE", 5000),
        ("ticket_state", "BASE TABLE", 12), ("ticket_state_type", "BASE TABLE", 7), ("ticket_priority", "BASE TABLE", 5),
        ("ticket_type", "BASE TABLE", 4), ("service", "BASE TABLE", 8),
        ("sla", "BASE TABLE", 6), ("link_object", "BASE TABLE", 8000),
        ("link_object_type", "BASE TABLE", 3), ("link_type", "BASE TABLE", 5),
        ("link_state", "BASE TABLE", 2), ("ticket_history", "BASE TABLE", 100000),
        ("article", "BASE TABLE", 20000), ("dynamic_field", "BASE TABLE", 10),
        ("dynamic_field_value", "BASE TABLE", 200), ("users", "BASE TABLE", 20),
        ("configitem", "BASE TABLE", 3000), ("general_catalog", "BASE TABLE", 400),
    ]
    definitions = {
        "queue": ["id", "name"],
        "ticket": ["id", "tn", "queue_id", "state_id", "priority_id", "type_id", "service_id", "sla_id", "create_time", "change_time", "title"],
        "ticket_state": ["id", "name", "type_id", "valid_id"], "ticket_state_type": ["id", "name"], "ticket_priority": ["id", "name"],
        "ticket_type": ["id", "name"], "service": ["id", "name"], "sla": ["id", "name"],
        "link_object": ["id", "source_object_id", "source_key", "target_object_id", "target_key", "type_id", "state_id"],
        "link_object_type": ["id", "name"], "link_type": ["id", "name"], "link_state": ["id", "name"],
        "ticket_history": ["id", "ticket_id", "history_type_id"],
        "article": ["id", "ticket_id", "body", "a_subject"],
        "dynamic_field": ["id", "name"], "dynamic_field_value": ["id", "object_id", "field_id", "value_text"],
        "users": ["id", "login", "pw"],
        "configitem": ["id", "configitem_number", "class_id"],
        "general_catalog": ["id", "general_catalog_class", "name"],
    }
    all_columns = []
    schemas = {}
    for table, names in definitions.items():
        schemas[table] = [{"column": name, "type": "varchar(255)", "nullable": "YES", "key": ""} for name in names]
        for position, name in enumerate(names, 1):
            all_columns.append({"TABLE_NAME": table, "COLUMN_NAME": name, "COLUMN_TYPE": "varchar(255)", "IS_NULLABLE": "YES", "COLUMN_KEY": "", "ORDINAL_POSITION": position})
    return tables, all_columns, schemas


class FakeOTRSClient:
    def __init__(self):
        self.tables, self.all_columns, self.schemas = schema_fixture()
        self.queries = []

    def get_server_metadata(self):
        return {"database_name": "otrs_test", "server_version": "MariaDB test", "character_set": "utf8mb4", "collation": "utf8mb4_general_ci"}

    def list_tables(self, database=None):
        return [{"name": name, "type": kind, "estimated_rows": rows} for name, kind, rows in self.tables]

    def get_all_columns(self, database=None):
        return self.all_columns

    def get_table_schema(self, table, database=None):
        return self.schemas[table]

    def get_table_indexes(self, table, database=None):
        return [{"name": "PRIMARY", "column": "id", "unique": True}]

    def get_foreign_keys(self, table, database=None):
        return []

    def execute_select(self, sql, params=()):
        self.queries.append((sql, params))
        compact = " ".join(sql.split())
        if "FROM `queue`" in compact and "LIKE" not in compact:
            return [{"queue_id": 7, "queue_name": "NOC - ATACADO"}]
        if "FROM `queue`" in compact:
            return []
        if "FROM `ticket`" in compact:
            return [
                {"id": 101, "tn": "2026102300000001", "queue_id": 7, "state_id": 2, "priority_id": 2, "type_id": 1, "service_id": 1, "sla_id": 1, "create_time": "2026-10-22"},
                {"id": 102, "tn": "2026102300000002", "queue_id": 7, "state_id": 3, "priority_id": 3, "type_id": 1, "service_id": 1, "sla_id": None, "create_time": "2026-10-23"},
                {"id": 103, "tn": "2026102300000003", "queue_id": 7, "state_id": 2, "priority_id": 2, "type_id": 1, "service_id": 1, "sla_id": None, "create_time": "2026-10-23"},
            ]
        if "FROM `link_object_type`" in compact:
            return [{"object_id": 1, "object_name": "Ticket"}, {"object_id": 2, "object_name": "ITSMConfigItem"}]
        if "FROM `link_object`" in compact:
            return [
                {"source_object_id": 1, "source_key": "101", "target_object_id": 2, "target_key": "4633", "type_id": 1, "state_id": 1},
                {"source_object_id": 1, "source_key": "101", "target_object_id": 2, "target_key": "4635", "type_id": 1, "state_id": 1},
                {"source_object_id": 2, "source_key": "999", "target_object_id": 1, "target_key": "102", "type_id": 2, "state_id": 1},
            ]
        if "FROM `link_type`" in compact:
            return [{"relation_id": 1, "relation_name": "Normal", "valid_id": 1}, {"relation_id": 2, "relation_name": "DependsOn", "valid_id": 1}]
        if "FROM `link_state`" in compact:
            return [{"relation_id": 1, "relation_name": "Valid", "valid_id": 1}, {"relation_id": 2, "relation_name": "Invalid", "valid_id": 2}]
        if "FROM `ticket_state_type`" in compact:
            return [{"type_id": 2, "type_name": "open"}, {"type_id": 3, "type_name": "closed"}]
        if "FROM `ticket_state`" in compact:
            return [{"dimension_id": 2, "dimension_name": "open", "state_type_id": 2, "valid_id": 1}, {"dimension_id": 3, "dimension_name": "closed successful", "state_type_id": 3, "valid_id": 1}]
        if any(f"FROM `{name}`" in compact for name in ("ticket_priority", "ticket_type", "service", "sla")):
            return [{"dimension_id": 1, "dimension_name": "General"}, {"dimension_id": 2, "dimension_name": "High"}]
        if "FROM `ticket_history`" in compact or "FROM `article`" in compact:
            return [{"row_count": 5}]
        if "FROM `dynamic_field`" in compact:
            return [{"field_name": "ConfigItemID"}, {"field_name": "Projeto"}]
        if "FROM `configitem` c JOIN `general_catalog` g" in compact:
            return [
                {"configitem_id": "4633", "class_name": "Links de internet"},
                {"configitem_id": "4635", "class_name": "Links de internet"},
                {"configitem_id": "999", "class_name": "Pop"},
            ]
        return []


class FakeCMDBClient:
    def get_items(self, identifiers):
        return [
            {"ConfigItemID": "4633", "Number": "36131000003", "Class": "Links de internet", "Name": "Link A", "CIXMLData": {"Designacao": "Circuit A", "ISP": "6804"}},
            {"ConfigItemID": "4635", "Number": "36131000005", "Class": "Links de internet", "Name": "Link B", "CIXMLData": {"Designacao": "Circuit B", "SenhaPPOE": "SUPER_SECRET_PASSWORD"}},
        ]


class OTRSStudyTests(TestCase):
    def setUp(self):
        self.client = FakeOTRSClient()

    def test_exact_queue_resolution_and_current_ticket_count(self):
        result = OTRSStudyService(self.client, progress=lambda _: None).run("NOC - ATACADO")
        self.assertEqual(result["queue"]["id"], 7)
        self.assertEqual(result["ticket"]["count"], 3)
        self.assertEqual(result["ticket"]["state_ids"], {"2": 2, "3": 1})

    def test_association_is_proven_in_both_directions_with_multiple_and_zero_ci(self):
        result = OTRSStudyService(self.client, progress=lambda _: None).run()
        rel = result["relationship"]
        self.assertEqual(rel["status"], "confirmada")
        self.assertEqual(rel["directions"], {"Ticket→ConfigItem": 2, "ConfigItem→Ticket": 1})
        self.assertEqual(rel["tickets_with_ci"], 2)
        self.assertEqual(rel["tickets_without_ci"], 1)
        self.assertEqual(rel["tickets_one_ci"], 1)
        self.assertEqual(rel["tickets_multiple_ci"], 1)
        self.assertEqual(rel["association_count"], 3)
        self.assertEqual(result["local_cmdb"]["class_counts"], {"Links de internet": 2, "Pop": 1})
        self.assertEqual(result["open_review"]["open_with_link"], 1)
        self.assertEqual(result["open_review"]["open_ticket_count"], 2)
        self.assertEqual(result["open_review"]["open_with_any_configitem"], 1)
        self.assertEqual(result["open_review"]["open_without_configitem"], 1)

    def test_inactive_relation_state_is_excluded_from_primary_counts(self):
        client = FakeOTRSClient()
        original = client.execute_select

        def with_invalid_state(sql, params=()):
            rows = original(sql, params)
            if "FROM `link_object`" in sql:
                rows[0]["state_id"] = 2
            return rows

        client.execute_select = with_invalid_state
        result = OTRSStudyService(client, progress=lambda _: None).run()
        self.assertEqual(result["relationship"]["invalid_state_count"], 1)
        self.assertEqual(result["relationship"]["association_count"], 2)

    def test_cmdb_check_is_bounded_and_report_omits_secret_article_body_and_user_hash(self):
        result = OTRSStudyService(self.client, cmdb_client=FakeCMDBClient(), progress=lambda _: None).run()
        self.assertEqual(result["cmdb"]["identifier_used"], "ConfigItemID")
        self.assertEqual(result["cmdb"]["links"], 2)
        self.assertNotIn("SUPER_SECRET_PASSWORD", result["report"])
        self.assertNotIn("<body-value>", result["report"])
        self.assertNotIn("<password-hash>", result["report"])
        self.assertTrue(all("`body`" not in sql for sql, _ in self.client.queries))
        self.assertTrue(all("`pw`" not in sql for sql, _ in self.client.queries))

    def test_missing_queue_is_not_replaced_with_a_guess(self):
        client = FakeOTRSClient()
        original = client.execute_select

        def no_queue(sql, params=()):
            if "FROM `queue`" in sql:
                return []
            return original(sql, params)

        client.execute_select = no_queue
        result = OTRSStudyService(client, progress=lambda _: None).run("NOC - ATACADO")
        self.assertIsNone(result["queue"]["id"])
        self.assertEqual(result["queue"]["status"], "sem correspondência exata")
        self.assertEqual(result["ticket"]["count"], 0)

    def test_missing_queue_table_is_reported_without_assuming_a_name(self):
        client = FakeOTRSClient()
        client.tables = [row for row in client.tables if row[0] != "queue"]
        result = OTRSStudyService(client, progress=lambda _: None).run("NOC - ATACADO")
        self.assertIsNone(result["queue"]["id"])
        self.assertEqual(result["queue"]["status"], "tabela queue não encontrada")

    def test_schema_allowlist_rejects_unknown_or_sensitive_identifiers(self):
        study = OTRSStudyService(self.client)
        study.tables = {"users": {"name": "users"}}
        study.columns = {"users": [{"column": "id"}, {"column": "pw"}]}
        with self.assertRaises(ValueError):
            study._qtable("users; DROP TABLE users")
        with self.assertRaises(ValueError):
            study._qcol("users", "pw")

    def test_report_does_not_claim_a_project_source_or_operational_sync(self):
        result = OTRSStudyService(self.client, progress=lambda _: None).run()
        self.assertIn("Fonte oficial de Projeto: **NÃO ENCONTRADA**", result["report"])
        self.assertIn("nem conectou tickets às métricas operacionais", result["report"])
        self.assertEqual(result["database"]["database_name"], "otrs_test")
        self.assertEqual(len(result["tables"]), len(self.client.tables))


class OTRSReadOnlyGuardTests(TestCase):
    def setUp(self):
        self.client = OTRSReadOnlyClient(host="db.example", username="reader", password="private", database="otrs", connection_factory=lambda: None)

    def test_only_select_without_side_effects_or_multiple_statements_is_accepted(self):
        self.client._connection = lambda: None
        for sql in (
            "INSERT INTO ticket VALUES (1)", "UPDATE ticket SET title='x'", "DELETE FROM ticket",
            "ALTER TABLE ticket ADD x INT", "DROP TABLE ticket", "CREATE TABLE x (id INT)",
            "TRUNCATE ticket", "REPLACE INTO ticket VALUES (1)", "SELECT id FROM ticket; DELETE FROM ticket",
            "SELECT pw FROM users", "SELECT body FROM article", "SELECT id FROM ticket FOR UPDATE",
        ):
            with self.subTest(sql=sql), self.assertRaises(OTRSDatabaseError):
                self.client.execute_select(sql)

    def test_sensitive_names_are_not_present_in_error_output(self):
        with self.assertRaises(OTRSDatabaseError) as caught:
            self.client.execute_select("SELECT pw FROM users")
        encoded = json.dumps({"exception": str(caught.exception), "sql": ""})
        self.assertNotIn("SUPER_SECRET_PASSWORD", encoded)
        self.assertNotIn("FAKE_TOKEN_123", encoded)


class OTRSReadOnlySessionTests(TestCase):
    def test_study_queries_reuse_one_session_connection(self):
        from aplicativos.integracoes.test_clients import FakeConnection

        connections = []

        def factory():
            connection = FakeConnection()
            connections.append(connection)
            return connection

        client = OTRSReadOnlyClient(host="db.example", username="reader", password="private", database="otrs", connection_factory=factory)
        with client.read_only_session():
            client.test_connection()
            client.list_tables()
            client.get_table_schema("users")
        self.assertEqual(len(connections), 1)
        self.assertTrue(connections[0].closed)
