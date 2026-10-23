from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from openpyxl import Workbook
from aplicativos.auditoria.models import AuditEvent

from .classification import detect_operator, detect_project
from .models import CMDBImport, CMDBLink, CMDBLinkChange, Operadora, Projeto, Provider
from .services.cmdb.excel_provider import ExcelCMDBProvider, FIELD_MAP, SENSITIVE_HEADERS, normalize_provider
from .services.cmdb.sync import inspect_items, sync_items


def workbook_bytes(rows=None, headers=None):
    workbook = Workbook()
    sheet = workbook.active
    headers = headers or [*FIELD_MAP, *SENSITIVE_HEADERS]
    sheet.append(headers)
    rows = rows or [default_row()]
    for row in rows:
        sheet.append([row.get(header, "") for header in headers])
    content = BytesIO()
    workbook.save(content)
    return content.getvalue()


def default_row(**changes):
    row = {
        "Classe": "Links de internet", "Estado de Incidente": "Operational",
        "Nome": "VIVO - BRADESCO", "ConfigItem#": "36131003500",
        "Estado de Implantação": "Operacional", "Versão": "31098",
        "Hora de Criação": "2026-10-22 08:51:57", "Designação ARION": "VIVO.SP.BLIVR000001",
        "CNPJ ARION": "N/A", "Endereço": "Rua Um, 10", "Cidade": "São Paulo",
        "Estado": "SP", "Cliente": "37", "Circuito": "CIR-01",
        "ISP": "MINAS TELECOM (36132001342)", "Velocidade": "100 MB",
        "Range IP": "192.168.1.1", "Tipo": "BANDA LARGA", "Número de Contrato": "C-01",
        "Designação da Operadora": "N/A", "Identificação (BRAD, SIGLA, AG)": "N/A",
        "Horário de Funcionamento": "Comercial", "Usuário PPOE": "usuario-secreto",
        "Senha PPOE": "senha-secreta", "Observação (Particularidade da ISP)": "Observação original",
    }
    row.update(changes)
    return row


class ClassificationTests(TestCase):
    def test_explicit_operator_and_project_are_detected(self):
        self.assertEqual(detect_operator({"name": "FUST UBS - CLARO.PR.BLIVR001045"}), "CLARO")
        self.assertEqual(detect_project({"name": "REMANEJAMENTO DE CIRCUITO - CAIXA ECONOMICA"}), "Caixa Econômica")
        self.assertEqual(detect_operator({"name": "VIVO - ARCOS DOURADOS"}), "VIVO")
        self.assertEqual(detect_project({"name": "VIVO - ARCOS DOURADOS"}), "Arcos Dourados")

    def test_unknown_or_conflicting_classification_is_not_guessed(self):
        self.assertIsNone(detect_operator({"name": "Circuito metropolitano sem operadora"}))
        self.assertIsNone(detect_project({"name": "Projeto sem nome explícito"}))
        self.assertIsNone(detect_operator({"name": "CLARO / VIVO - BRADESCO"}))

    def test_provider_normalization_keeps_business_variants_separate(self):
        name, normalized, config_id = normalize_provider("MINAS TELECOM (36132001342)")
        self.assertEqual((name, normalized, config_id), ("MINAS TELECOM", "minas telecom", "36132001342"))
        self.assertNotEqual(normalize_provider("VERO / AMERICANET")[1], normalize_provider("VERO")[1])
        self.assertEqual(normalize_provider("Tower Connection(WKE)")[0], "Tower Connection(WKE)")


class CMDBImportServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="cmdb-importer", password="Senha-segura-123")

    def parsed(self, rows=None, headers=None):
        provider = ExcelCMDBProvider(workbook_bytes(rows, headers), "fixture.xlsx")
        provider.load_items()
        self.assertTrue(provider.validate())
        items = provider.normalize()
        return provider, items

    def sync(self, provider, items, errors=None):
        return sync_items(items=items, filename=provider.filename, sha256=provider.sha256, imported_by=self.user, errors=errors or [])

    def test_valid_import_preserves_original_fields_but_drops_ppoe_credentials(self):
        provider, items = self.parsed()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["config_item_id"], "36131003500")
        self.assertEqual(items[0]["provider_name"], "MINAS TELECOM")
        self.assertEqual(items[0]["provider_cmdb_config_item_id"], "36132001342")
        self.assertEqual(items[0]["client_raw"], "37")
        self.assertEqual(items[0]["operadora_name"], "VIVO")
        self.assertEqual(items[0]["projeto_name"], "Bradesco")
        self.assertEqual(items[0]["source_created_at"].year, 2026)
        self.assertNotIn("Usuário PPOE", items[0]["source_payload"])
        self.assertNotIn("Senha PPOE", items[0]["source_payload"])
        preview = inspect_items(items)
        self.assertEqual(preview["new"][0]["config_item_id"], "36131003500")
        self.assertEqual(Provider.objects.count(), 0)
        batch = self.sync(provider, items)
        self.assertEqual(batch.new_count, 1)
        link = CMDBLink.objects.get(config_item_id="36131003500")
        self.assertNotIn("senha-secreta", str(link.source_payload))
        self.assertNotIn("usuario-secreto", str(link.source_payload))

    def test_config_item_is_unique_and_repeated_designations_are_allowed(self):
        second = default_row(**{"ConfigItem#": "36131003501"})
        provider, items = self.parsed([default_row(), second])
        self.sync(provider, items)
        self.assertEqual(CMDBLink.objects.count(), 2)
        self.assertEqual(CMDBLink.objects.values("designation_arion").distinct().count(), 1)
        with self.assertRaises(IntegrityError):
            CMDBLink.objects.create(config_item_id="36131003500")

    def test_reimport_is_unchanged_and_update_records_field_history(self):
        provider, items = self.parsed()
        self.sync(provider, items)
        same_provider, same_items = self.parsed()
        self.assertEqual(inspect_items(same_items)["updated"], [])
        second_batch = self.sync(same_provider, same_items)
        self.assertEqual(second_batch.unchanged_count, 1)
        self.assertEqual(CMDBLink.objects.count(), 1)

        changed_provider, changed_items = self.parsed([default_row(**{"Velocidade": "200 MB", "Versão": "31099"})])
        changed_batch = self.sync(changed_provider, changed_items)
        self.assertEqual(changed_batch.updated_count, 1)
        self.assertEqual(CMDBLink.objects.get().speed_raw, "200 MB")
        self.assertTrue(CMDBLinkChange.objects.filter(field_name="speed_raw", old_value="100 MB", new_value="200 MB").exists())

    def test_missing_config_item_header_blocks_file(self):
        headers = [header for header in FIELD_MAP if header != "ConfigItem#"]
        provider = ExcelCMDBProvider(workbook_bytes(headers=headers), "invalid.xlsx")
        provider.load_items()
        self.assertFalse(provider.validate())
        self.assertTrue(any("ConfigItem#" in error["message"] for error in provider.errors))
        self.assertEqual(provider.normalize(), [])

    def test_duplicate_config_item_in_one_file_is_reported_and_not_repeated(self):
        provider, items = self.parsed([default_row(), default_row(**{"Designação ARION": "OUTRO NOME"})])
        self.assertEqual(len(items), 1)
        self.assertEqual(len(provider.errors), 1)

    def test_non_link_classes_are_not_imported(self):
        provider, items = self.parsed([default_row(**{"Classe": "Computer"})])
        self.assertEqual(items, [])
        self.assertIn("Classe não importada", provider.errors[0]["message"])

    def test_invalid_state_is_kept_raw_and_full_state_name_is_normalized(self):
        _provider, items = self.parsed([default_row(**{"Estado": "São Paulo"})])
        self.assertEqual(items[0]["uf"], "SP")
        _provider, items = self.parsed([default_row(**{"Estado": "VCP"})])
        self.assertEqual(items[0]["uf"], "")
        self.assertEqual(items[0]["uf_raw"], "VCP")


class CMDBViewsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="base-user", password="Senha-segura-123")

    def test_base_and_import_require_login(self):
        for url_name in ("base_links:index", "base_links:import", "base_links:map-aggregates"):
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 302)
            self.assertIn("/login/", response.url)

    def test_upload_preview_does_not_write_and_confirmation_imports(self):
        permission = Permission.objects.get(content_type__app_label="configuracoes", codename="import_cmdb")
        self.user.user_permissions.add(permission)
        self.client.force_login(self.user)
        response = self.client.post(reverse("base_links:import"), {"file": SimpleUploadedFile("fixture.xlsx", workbook_bytes(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Confirmar atualização")
        self.assertEqual(CMDBLink.objects.count(), 0)
        token = self.client.session["cmdb_import_preview_token"]
        response = self.client.post(reverse("base_links:confirm"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CMDBLink.objects.count(), 1)
        self.assertEqual(CMDBImport.objects.count(), 1)
        event = AuditEvent.objects.get(action="CMDB_IMPORT")
        self.assertEqual(event.user, self.user)
        self.assertEqual(event.metadata["import_id"], CMDBImport.objects.get().pk)
        self.assertNotIn("senha-secreta", str(event.metadata))

    def test_base_search_filters_and_pagination(self):
        self.client.force_login(self.user)
        provider = Provider.objects.create(name="MINAS TELECOM", normalized_name="minas telecom")
        operadora = Operadora.objects.create(name="VIVO", normalized_name="vivo")
        projeto = Projeto.objects.create(name="Bradesco", normalized_name="bradesco")
        batch = CMDBImport.objects.create(filename="base.xlsx", file_sha256="a" * 64, imported_by=self.user)
        for index in range(60):
            CMDBLink.objects.create(
                config_item_id=str(36131000000 + index), designation_arion=f"BD{index:07d}", isp_raw=f"Carrier {index}",
                name=f"Link São Paulo {index}", city="São Paulo", uf="SP", deployment_state="Operacional",
                incident_state="Operational", provider=provider, operadora=operadora, projeto=projeto,
                last_seen_import=batch,
            )
        response = self.client.get(reverse("base_links:index"), {"q": "BD0000001", "uf": "SP"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        self.assertContains(response, 'data-clear-search')
        self.assertContains(response, 'view=providers')
        self.assertContains(response, '</svg>Por provedor</a>')
        self.assertContains(response, 'value="500"')
        response = self.client.get(reverse("base_links:index"), {"page_size": 25})
        self.assertEqual(response.context["page_obj"].paginator.num_pages, 3)
        response = self.client.get(reverse("base_links:index"), {"page_size": 500, "q": "Carrier 1"})
        self.assertEqual(response.context["page_size"], 500)
        self.assertEqual(response.context["page_obj"].paginator.count, 11)
        response = self.client.get(reverse("base_links:index"), {"operadora": operadora.pk, "classification_status": "classified"})
        self.assertEqual(response.context["page_obj"].paginator.count, 0)

    def test_map_aggregate_groups_real_links_by_state_and_operator(self):
        self.client.force_login(self.user)
        operator = Operadora.objects.create(name="CLARO", normalized_name="claro")
        batch = CMDBImport.objects.create(filename="base.xlsx", file_sha256="b" * 64, imported_by=self.user)
        CMDBLink.objects.create(config_item_id="1", uf="SP", operadora=operator, last_seen_import=batch)
        response = self.client.get(reverse("base_links:map-aggregates"))
        self.assertEqual(response.json()["states"]["SP"]["claro"], 1)
        self.assertFalse(response.json()["ticket_data_available"])
