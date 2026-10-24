import json
from unittest import TestCase
from unittest.mock import Mock

from aplicativos.integracoes.clients.cmdb import CMDBClient
from aplicativos.integracoes.clients.otrs import OTRSReadOnlyClient
from aplicativos.integracoes.services.errors import (
    CMDBAuthenticationError,
    CMDBTimeoutError,
    OTRSAuthenticationError,
    OTRSConnectionRefusedError,
    OTRSCredentialInvalidError,
    OTRSDatabaseError,
    OTRSDatabaseNotFoundError,
    OTRSDriverError,
    OTRSHostUnreachableError,
    OTRSTimeoutError,
)


class FakeHTTPResponse:
    def __init__(self, body):
        self.body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.body[:size]


class CMDBClientTests(TestCase):
    def test_search_posts_genericinterface_config_item_payload_and_a_bounded_limit(self):
        opener = Mock()
        opener.open.return_value = FakeHTTPResponse({"ConfigItem": [{"ConfigItemID": "4", "Name": "Link"}]})
        client = CMDBClient(base_url="https://cmdb.example/Webservice/", username="reader", password="private", opener=opener)

        result = client.search_items(class_name="Link", number="L-1", limit=999)

        request, = opener.open.call_args.args
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload, {"ConfigItem": {"Class": "Link", "Number": "L-1", "Limit": 100}, "UserLogin": "reader", "Password": "private"})
        self.assertNotIn("Authorization", request.headers)
        self.assertTrue(request.full_url.endswith("Webservice/CMDB/ConfigItemSearch"))
        self.assertEqual(result[0]["ConfigItemID"], "4")

    def test_get_splits_requested_ids_into_configured_batches(self):
        opener = Mock()
        opener.open.side_effect = [FakeHTTPResponse({"Items": [{"ConfigItemID": "1"}]}), FakeHTTPResponse({"Items": [{"ConfigItemID": "2"}]})]
        client = CMDBClient(base_url="https://cmdb.example/", username="reader", password="private", batch_size=1, opener=opener)

        result = client.get_items(["1", "2"])

        self.assertEqual(len(result), 2)
        self.assertEqual([json.loads(call.args[0].data.decode())["ConfigItemID"] for call in opener.open.call_args_list], ["1", "2"])

    def test_base_url_with_or_without_webservice_suffix_produces_correct_search_and_get_urls(self):
        for base_url in ("https://cmdb.example/otrs/nph-genericinterface.pl/Webservice", "https://cmdb.example/otrs/nph-genericinterface.pl/Webservice/"):
            with self.subTest(base_url=base_url):
                opener = Mock()
                opener.open.side_effect = [FakeHTTPResponse({"ConfigItemIDs": [4633]}), FakeHTTPResponse({"ConfigItem": [{"ConfigItemID": "4633"}]})]
                client = CMDBClient(base_url=base_url, username="configured-user", password="private", opener=opener)
                client.search_items(class_name="Links de internet", limit=1)
                search_request, get_request = [call.args[0] for call in opener.open.call_args_list]
                self.assertEqual(search_request.full_url, "https://cmdb.example/otrs/nph-genericinterface.pl/Webservice/CMDB/ConfigItemSearch")
                self.assertEqual(get_request.full_url, "https://cmdb.example/otrs/nph-genericinterface.pl/Webservice/CMDB/ConfigItemGet")
                search_payload = json.loads(search_request.data.decode())
                self.assertEqual(search_payload["ConfigItem"], {"Class": "Links de internet", "Limit": 1})
                self.assertEqual(search_payload["UserLogin"], "configured-user")
                self.assertEqual(json.loads(get_request.data.decode())["ConfigItemID"], "4633")

    def test_connection_accepts_nonempty_and_empty_config_item_ids_without_get(self):
        for ids in ([4633], []):
            with self.subTest(ids=ids):
                opener = Mock()
                opener.open.return_value = FakeHTTPResponse({"ConfigItemIDs": ids})
                client = CMDBClient(base_url="https://cmdb.example/Webservice/", username="reader", password="private", opener=opener)
                self.assertTrue(client.test_connection())
                self.assertEqual(opener.open.call_count, 1)
                payload = json.loads(opener.open.call_args.args[0].data.decode())
                self.assertEqual(payload["ConfigItem"], {"Class": "Links de internet", "Limit": 1})

    def test_read_only_study_search_supports_large_limit_and_omitted_limit(self):
        opener = Mock()
        opener.open.side_effect = [FakeHTTPResponse({"ConfigItemIDs": ["1"]}), FakeHTTPResponse({"ConfigItemIDs": ["2"]})]
        client = CMDBClient(base_url="https://cmdb.example/", username="reader", password="private", opener=opener)

        client.search_item_ids(class_name="Links de internet", limit=5000)
        client.search_item_ids(class_name="Links de internet", limit=None)

        payloads = [json.loads(call.args[0].data.decode("utf-8"))["ConfigItem"] for call in opener.open.call_args_list]
        self.assertEqual(payloads, [
            {"Class": "Links de internet", "Limit": 5000},
            {"Class": "Links de internet"},
        ])

    def test_search_resolves_generic_interface_ids_through_config_item_get(self):
        opener = Mock()
        opener.open.side_effect = [
            FakeHTTPResponse({"Success": 1, "Data": {"ConfigItemID": ["11", "12"]}}),
            FakeHTTPResponse({"Success": 1, "Data": {"ConfigItem": [{"ConfigItemID": "11", "Name": "Link A"}, {"ConfigItemID": "12", "Name": "Link B"}]}}),
        ]
        client = CMDBClient(base_url="https://cmdb.example/", username="reader", password="private", batch_size=50, opener=opener)
        result = client.search_items(limit=2)
        self.assertEqual([item["Name"] for item in result], ["Link A", "Link B"])
        self.assertTrue(opener.open.call_args_list[0].args[0].full_url.endswith("ConfigItemSearch"))
        self.assertTrue(opener.open.call_args_list[1].args[0].full_url.endswith("ConfigItemGet"))

    def test_http_200_generic_interface_authentication_error_is_not_reported_as_empty_search(self):
        opener = Mock()
        opener.open.return_value = FakeHTTPResponse({"Success": 0, "Error": {"ErrorCode": "ConfigItemSearch.AuthFail", "ErrorMessage": "private provider details"}})
        client = CMDBClient(base_url="https://cmdb.example/", username="reader", password="private", opener=opener)
        with self.assertRaises(CMDBAuthenticationError) as caught:
            client.search_items()
        self.assertEqual(caught.exception.error_code, "ConfigItemSearch.AuthFail")
        self.assertNotIn("private provider details", caught.exception.safe_message)

    def test_authentication_and_timeout_errors_are_safe_domain_errors(self):
        import urllib.error

        opener = Mock()
        opener.open.side_effect = urllib.error.HTTPError("https://cmdb.example/", 401, "secret response", {}, None)
        client = CMDBClient(base_url="https://cmdb.example/", username="reader", password="private", opener=opener)
        with self.assertRaises(CMDBAuthenticationError):
            client.test_connection()
        opener.open.side_effect = TimeoutError("private timeout details")
        with self.assertRaises(CMDBTimeoutError):
            client.test_connection()

    def test_sanitizer_keeps_new_public_attributes_but_denies_sensitive_names(self):
        result = CMDBClient.sanitize_item({
            "ConfigItemID": "7", "Number": "L-2", "Name": "Metro", "Class": "Link",
            "Password": "top secret", "PortalPassword": "top secret", "UsuarioPortalOperadora": "portal-user",
            "CIXMLData": {"Designacao": "Circuito A", "ISP": "Operadora", "CNPJ": "123", "Equipamento": "router", "SenhaPPOE": "top secret", "UsuarioPortalOperadora": "portal-user", "RandomField": "hidden", "SessionCookie": "top secret"},
        })
        self.assertNotIn("Password", result)
        self.assertNotIn("UsuarioPortalOperadora", result)
        self.assertEqual(result["CIXMLData"], {"Designacao": "Circuito A", "ISP": "Operadora", "CNPJ": "123", "Equipamento": "router", "RandomField": "hidden"})
        self.assertNotIn("top secret", json.dumps(result))
        self.assertNotIn("portal-user", json.dumps(result))


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.query = ""
        self.params = ()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=()):
        self.query, self.params = query, params
        self.connection.queries.append((query, params))

    def fetchone(self):
        if "DATABASE()" in self.query:
            return {"database_name": "otrs", "server_version": "MariaDB 10.6", "server_time": "2026-10-24 12:00:00"}
        return {"connection_ok": 1}

    def fetchall(self):
        if "SCHEMATA" in self.query:
            return [{"SCHEMA_NAME": "otrs"}]
        if "information_schema.TABLES" in self.query:
            return [{"TABLE_NAME": "users", "TABLE_TYPE": "BASE TABLE", "TABLE_ROWS": 12}]
        if "information_schema.COLUMNS" in self.query:
            return [{"COLUMN_NAME": "pw", "COLUMN_TYPE": "varchar(64)", "IS_NULLABLE": "NO", "COLUMN_KEY": "", "COLUMN_DEFAULT": None, "EXTRA": ""}]
        if "information_schema.STATISTICS" in self.query:
            return [{"INDEX_NAME": "PRIMARY", "NON_UNIQUE": 0, "SEQ_IN_INDEX": 1, "COLUMN_NAME": "id", "INDEX_TYPE": "BTREE"}]
        if "KEY_COLUMN_USAGE" in self.query:
            return []
        if self.query.startswith("SELECT * FROM"):
            return [{"id": 1, "pw": "never expose", "token": "also private", "login": "reader"}]
        return []


class FakeConnection:
    def __init__(self):
        self.queries = []
        self.closed = False

    def cursor(self):
        return FakeCursor(self)

    def close(self):
        self.closed = True


class OTRSReadOnlyClientTests(TestCase):
    def setUp(self):
        self.connections = []

        def factory():
            connection = FakeConnection()
            self.connections.append(connection)
            return connection

        self.client = OTRSReadOnlyClient(host="db.example", username="reader", password="private", database="otrs", connection_factory=factory)

    def test_connection_and_schema_operations_use_only_read_only_or_select_statements(self):
        self.assertTrue(self.client.test_connection())
        tables = self.client.list_tables()
        columns = self.client.get_table_schema("users")
        indexes = self.client.get_table_indexes("users")
        foreign_keys = self.client.get_foreign_keys("users")
        self.assertEqual(tables[0]["name"], "users")
        self.assertEqual(columns[0]["column"], "pw")
        self.assertEqual(indexes[0]["name"], "PRIMARY")
        self.assertEqual(foreign_keys, [])
        all_queries = [query.upper().strip() for connection in self.connections for query, _ in connection.queries]
        self.assertTrue(all(query.startswith(("SELECT", "SET SESSION TRANSACTION READ ONLY")) for query in all_queries))
        self.assertTrue(all(connection.closed for connection in self.connections))

    def test_connection_checks_selected_database_and_server_metadata(self):
        self.assertTrue(self.client.test_connection())
        query = self.connections[0].queries[-1][0]
        self.assertIn("DATABASE()", query)
        self.assertIn("VERSION()", query)
        self.assertIn("NOW()", query)

        self.client.database = "another_database"
        with self.assertRaises(OTRSDatabaseNotFoundError):
            self.client.test_connection()

    def test_driver_errors_have_specific_safe_categories(self):
        class DriverFailure(Exception):
            pass

        cases = (
            ((1045, "Access denied; password=never-show"), OTRSAuthenticationError),
            ((1049, "Unknown database otrs"), OTRSDatabaseNotFoundError),
            ((2003, "Can't connect [WinError 10061] Connection refused"), OTRSConnectionRefusedError),
            ((2003, "Can't connect [WinError 10060] timed out"), OTRSTimeoutError),
            ((2005, "Unknown MySQL server host"), OTRSHostUnreachableError),
            ((3024, "Query execution was interrupted"), OTRSTimeoutError),
            ((7777, "unexpected driver failure password=never-show"), OTRSDriverError),
        )
        for args, expected in cases:
            with self.subTest(code=args[0]):
                error = OTRSReadOnlyClient._mapped_error(DriverFailure(*args))
                self.assertIsInstance(error, expected)
                self.assertNotIn("never-show", error.safe_message)

    def test_password_must_be_decrypted_plaintext_string_without_line_breaks(self):
        for password in (b"encoded-bytes", "encoded\nvalue"):
            with self.subTest(password_type=type(password).__name__):
                with self.assertRaises(OTRSCredentialInvalidError) as caught:
                    OTRSReadOnlyClient(host="db.example", username="reader", password=password)
                self.assertNotIn("encoded", str(caught.exception))

    def test_sample_is_limited_and_sensitive_columns_are_masked(self):
        result = self.client.get_sample_rows("users", page_size=500)
        self.assertEqual(result[0]["pw"], "••••••")
        self.assertEqual(result[0]["token"], "••••••")
        self.assertEqual(result[0]["login"], "reader")
        sample_query = [query for connection in self.connections for query, _ in connection.queries if query.startswith("SELECT * FROM")][0]
        self.assertIn("LIMIT %s OFFSET %s", sample_query)
        sample_params = [params for connection in self.connections for query, params in connection.queries if query.startswith("SELECT * FROM")][0]
        self.assertEqual(sample_params, (50, 0))

    def test_table_identifier_must_be_discovered_and_supported(self):
        with self.assertRaises(OTRSDatabaseError):
            self.client.get_sample_rows("users; DROP TABLE users")
