import json
from unittest import TestCase

from aplicativos.integracoes.clients.cmdb import CMDBClient
from aplicativos.integracoes.services.cmdb_study import CMDBStudyService, _field_metrics


class FakeStudyClient:
    batch_size = 50
    MAX_STUDY_LIMIT = 5000

    def __init__(self, data):
        self.data = data
        self.search_calls = []

    def search_item_ids(self, *, class_name, limit):
        self.search_calls.append((class_name, limit))
        return list(self.data[class_name])

    def get_items(self, identifiers):
        return [self.data[identifier] for identifier in identifiers]


def sample_data():
    return {
        "Links de internet": ["internal-1", "internal-2", "internal-3", "internal-4"],
        "Operadoras": ["shared", "operator-2", "operator-3"],
        "internal-1": {
            "ConfigItemID": "internal-1", "Number": "0001", "Name": "Link confidential label",
            "Class": "Links de internet", "DefinitionID": "19", "VersionID": "2", "LastVersionID": "2",
            "CurDeplState": "Operacional", "CIXMLData": {"Tipo": "DEDICADO", "ISP": "shared", "MACAddress": "aa:bb", "DynamicNew": "present", "SenhaPPOE": "SUPER_SECRET_TEST"},
        },
        "internal-2": {
            "ConfigItemID": "internal-2", "Number": "2", "DefinitionID": "33", "VersionID": "3", "LastVersionID": "4",
            "CIXMLData": {"Tipo": "BANDA LARGA", "ISP": "N-2", "ExtraField": "x"},
        },
        "internal-3": {
            "ConfigItemID": "internal-3", "Number": "3", "DefinitionID": "33",
            "CIXMLData": {"ISP": "unresolved-isp", "SenhaPortalOperadora": "OTHER_SECRET_TEST"},
        },
        "internal-4": {"ConfigItemID": "internal-4", "Number": "4", "DefinitionID": "33", "CIXMLData": {"ISP": ""}},
        "shared": {"ConfigItemID": "shared", "Number": "N-1", "Name": "Operator One", "DefinitionID": "8", "CIXMLData": {"SenhaPortalOperadora": "OTHER_SECRET_TEST"}},
        "operator-2": {"ConfigItemID": "operator-2", "Number": "shared", "Name": "Operator Two", "DefinitionID": "8"},
        "operator-3": {"ConfigItemID": "operator-3", "Number": "N-2", "Name": "Operator Three", "DefinitionID": "9"},
    }


class CMDBStudyServiceTests(TestCase):
    def test_study_inventories_dynamic_fields_versions_states_and_exact_base_mapping(self):
        client = FakeStudyClient(sample_data())
        base = [
            {"config_item_id": "0001", "designation_arion": "circuit-1", "name": "Link confidential label"},
            {"config_item_id": "2", "designation_arion": "other", "name": "other"},
            {"config_item_id": "0002", "designation_arion": "not a numeric match"},
        ]

        result = CMDBStudyService(client, progress=lambda _: None, retry_delay=0).run(base)

        fields = result["links"]["fields"]
        self.assertIn("DynamicNew", fields)
        self.assertIn("ExtraField", fields)
        self.assertEqual(fields["DynamicNew"]["exists"], 1)
        self.assertEqual(fields["DynamicNew"]["filled"], 1)
        self.assertEqual(result["links"]["definitions"]["19"]["count"], 1)
        self.assertEqual(result["links"]["states"]["CurDeplState"], {"Operacional": 1})
        self.assertEqual(result["links"]["versions"]["same"], 1)
        self.assertEqual(result["links"]["versions"]["different"], 1)
        self.assertEqual(result["comparison"]["matches"], 2)
        self.assertEqual(result["comparison"]["base_only"], 1)
        self.assertEqual(result["relation"]["counts"]["ambiguous"], 1)
        self.assertEqual(result["relation"]["counts"]["Number"], 1)
        self.assertEqual(result["relation"]["counts"]["unresolved"], 1)
        self.assertEqual(result["relation"]["counts"]["empty"], 1)
        self.assertEqual(result["relation"]["counts"]["with_isp"], 3)
        self.assertIn("19", result["links"]["definitions"])
        self.assertIn("33", result["links"]["definitions"])
        self.assertEqual(client.search_calls[-1], ("Operadoras", None))
        self.assertNotIn("items", result["links"])

    def test_sensitive_fields_are_only_counted_and_never_serialized_or_logged(self):
        result = CMDBStudyService(FakeStudyClient(sample_data()), progress=lambda _: None, retry_delay=0).run([])
        encoded = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("SUPER_SECRET_TEST", encoded)
        self.assertNotIn("OTHER_SECRET_TEST", encoded)
        self.assertEqual(result["links"]["fields"]["SenhaPPOE"]["filled"], 1)
        self.assertTrue(result["links"]["fields"]["SenhaPPOE"]["sensitive"])
        self.assertIn("[PROTEGIDO]", result["report"])
        self.assertIn("### Versionamento", result["report"])
        self.assertIn("## Qualidade de dados", result["report"])
        self.assertIn("## Matriz de mapeamento", result["report"])
        self.assertIn("## Guia para investigacao OTRS", result["report"])
        self.assertNotIn("\\n|", result["report"])

    def test_search_and_get_shapes_study_sanitizer_without_changing_ui_sanitizer(self):
        raw = {
            "ConfigItemID": "1", "Number": "001", "DynamicTopLevel": "value",
            "PortalPassword": "TOP_SECRET", "CIXMLData": {"SenhaPPOE": "SUPER_SECRET_TEST", "Safe": "yes"},
        }
        study = CMDBClient.sanitize_study_items([raw])[0]
        normal = CMDBClient.sanitize_items([raw])[0]

        self.assertEqual(study["DynamicTopLevel"], "value")
        self.assertEqual(study["PortalPassword"], "[PROTEGIDO]")
        self.assertEqual(study["CIXMLData"]["SenhaPPOE"], "[PROTEGIDO]")
        self.assertNotIn("DynamicTopLevel", normal)
        self.assertNotIn("TOP_SECRET", json.dumps(study))
        self.assertNotIn("SUPER_SECRET_TEST", json.dumps(study))

    def test_unmatched_isp_is_not_coerced_to_numeric_or_guessed(self):
        links = [{"ConfigItemID": "l1", "CIXMLData": {"ISP": "0007"}}]
        operators = [{"ConfigItemID": "7", "Number": "7", "Name": "Operator"}]

        result = CMDBStudyService._resolve_isp(links, operators)

        self.assertEqual(result["counts"]["unresolved"], 1)
        self.assertEqual(result["conclusion"], "inconclusive")
