import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import RequestFactory, TestCase
from django.urls import reverse

from aplicativos.auditoria.models import AuditEvent
from aplicativos.auditoria.services import AuditService, sanitize_metadata
from aplicativos.base_links.models import Operadora, Projeto
from aplicativos.painel.models import SavedAnalyticsView


class AuditServiceTests(TestCase):
    def test_nested_metadata_is_json_safe_and_credential_keys_are_removed(self):
        metadata = {
            "safe": "ok", "password": "one", "new_password": "two", "api_key": "three",
            "nested": {"client_secret": "four", "authorization": "five", "sessionid": "six", "count": 2},
            "rows": [{"refresh-token": "seven", "name": "visible"}],
        }
        cleaned = sanitize_metadata(metadata)
        self.assertEqual(cleaned, {"safe": "ok", "nested": {"count": 2}, "rows": [{"name": "visible"}]})
        event = AuditService.record(category="TEST", action="SANITIZE", metadata=metadata)
        event.refresh_from_db()
        serialized = json.dumps(event.metadata)
        for secret in ("one", "two", "three", "four", "five", "six", "seven"):
            self.assertNotIn(secret, serialized)

    def test_http_context_captures_remote_ip_and_user_agent_but_not_anonymous_actor(self):
        request = RequestFactory().get("/", HTTP_USER_AGENT="Arion test agent")
        request.user = type("Anonymous", (), {"is_authenticated": False})()
        event = AuditService.record(request=request, category="TEST", action="HTTP")
        self.assertEqual(event.ip_address, "127.0.0.1")
        self.assertEqual(event.user_agent, "Arion test agent")
        self.assertIsNone(event.user)


class AuditEventsIntegrationTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.admin = self.User.objects.create_superuser(username="audit-admin", email="admin@example.com", password="Adm!nPass2026Strong")
        self.client.force_login(self.admin)
        AuditEvent.objects.all().delete()
        self.analyst_group = Group.objects.get(name="Analista NOC")
        self.auditor_group = Group.objects.get(name="Consulta / Auditoria")

    def test_user_create_update_activation_group_and_scope_events(self):
        created = self.client.post(reverse("configuracoes:user-create"), {
            "username": "audit-target", "first_name": "Ana", "last_name": "Silva", "email": "ana@example.com",
            "password1": "Initial!Password2026", "password2": "Initial!Password2026",
            "group": self.analyst_group.pk, "is_active": "on",
        })
        self.assertEqual(created.status_code, 302)
        target = self.User.objects.get(username="audit-target")
        event = AuditEvent.objects.get(action="USER_CREATED")
        self.assertEqual(event.user, self.admin)
        self.assertEqual(event.object_id, str(target.pk))
        self.assertEqual(event.metadata["group"], self.analyst_group.name)
        self.assertNotIn("password", json.dumps(event.metadata).casefold())

        operator = Operadora.objects.create(name="Claro", normalized_name="claro")
        project = Projeto.objects.create(name="Projeto A", normalized_name="projeto-a")
        url = reverse("configuracoes:user-edit", args=(target.pk,))
        changed = self.client.post(url, {
            "first_name": "Ana Maria", "last_name": "Silva", "email": "ana.maria@example.com", "is_active": "",
            "group": self.auditor_group.pk,
        })
        self.assertEqual(changed.status_code, 302)
        target.refresh_from_db()
        self.assertFalse(target.is_active)
        self.assertTrue(AuditEvent.objects.filter(action="USER_UPDATED", object_id=str(target.pk)).exists(), f"profile={target.first_name!r}/{target.email!r}; events={list(AuditEvent.objects.values_list('action', 'object_id', 'metadata'))}")
        group_event = AuditEvent.objects.get(action="GROUP_CHANGED", object_id=str(target.pk))
        self.assertEqual(group_event.metadata, {"before": self.analyst_group.name, "after": self.auditor_group.name})
        scope_url = reverse("configuracoes:scope-edit", args=(self.auditor_group.pk,))
        scope_changed = self.client.post(scope_url, {"mode": "custom", "allowed_operators": [operator.pk], "allowed_projects": [project.pk]})
        self.assertEqual(scope_changed.status_code, 302)
        scope_event = AuditEvent.objects.get(action="DATA_SCOPE_CHANGED", object_id=str(self.auditor_group.pk))
        self.assertEqual(scope_event.metadata["before"]["mode"], "custom")
        self.assertEqual(scope_event.metadata["after"]["mode"], "custom")
        self.assertEqual(scope_event.metadata["after"]["operators"], [operator.name])
        self.assertEqual(scope_event.metadata["after"]["projects"], [project.name])
        self.assertTrue(AuditEvent.objects.filter(action="USER_DEACTIVATED", object_id=str(target.pk)).exists())

        activated = self.client.post(url, {
            "first_name": "Ana Maria", "last_name": "Silva", "email": "ana.maria@example.com", "is_active": "on",
            "group": self.auditor_group.pk,
        })
        self.assertEqual(activated.status_code, 302)
        self.assertTrue(AuditEvent.objects.filter(action="USER_ACTIVATED", object_id=str(target.pk)).exists())

    def test_permission_changes_are_recorded_only_when_the_group_permission_set_changes(self):
        group = Group.objects.create(name="Temporary audit group")
        dashboard_permission = Permission.objects.get(content_type__app_label="configuracoes", codename="view_dashboard")
        base_permission = Permission.objects.get(content_type__app_label="configuracoes", codename="view_base")
        group.permissions.add(dashboard_permission)
        url = reverse("configuracoes:group-edit", args=(group.pk,))
        response = self.client.post(url, {"name": group.name, "permissions": [dashboard_permission.pk]})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AuditEvent.objects.filter(action="PERMISSIONS_CHANGED").exists())
        response = self.client.post(url, {"name": group.name, "permissions": [base_permission.pk]})
        self.assertEqual(response.status_code, 302)
        event = AuditEvent.objects.get(action="PERMISSIONS_CHANGED")
        self.assertEqual(event.metadata["permissions_before"], ["view_dashboard"])
        self.assertEqual(event.metadata["permissions_after"], ["view_base"])

    def test_password_change_never_records_password_values(self):
        response = self.client.post(reverse("configuracoes:security"), {
            "old_password": "Adm!nPass2026Strong", "new_password1": "Another!StrongPass2026", "new_password2": "Another!StrongPass2026",
        })
        self.assertEqual(response.status_code, 302)
        event = AuditEvent.objects.get(action="PASSWORD_CHANGED")
        serialized = json.dumps(event.metadata).casefold()
        self.assertNotIn("password", serialized)
        self.assertNotIn("another!strongpass2026", serialized)

    def test_saved_view_create_and_delete_are_audited(self):
        url = reverse("analytics-saved-views")
        response = self.client.post(url, data=json.dumps({"action": "save", "name": "Links por UF", "configuration": {"metric": "links", "group_by": "uf", "period": "2026-10"}}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        saved = SavedAnalyticsView.objects.get(pk=response.json()["id"])
        created = AuditEvent.objects.get(action="SAVED_VIEW_CREATED")
        self.assertEqual(created.object_id, str(saved.pk))
        response = self.client.post(url, data=json.dumps({"action": "delete", "id": saved.pk}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SavedAnalyticsView.objects.filter(pk=saved.pk).exists())
        self.assertTrue(AuditEvent.objects.filter(action="SAVED_VIEW_DELETED", object_id=str(saved.pk)).exists())

    def test_audit_list_filters_and_read_only_detail_render(self):
        event = AuditService.record(user=self.admin, category="ADMINISTRATION", action="USER_CREATED", description="Criou registro demo", metadata={"field": "visible"})
        list_response = self.client.get(reverse("configuracoes:audit"), {"q": "demo", "category": "ADMINISTRATION", "action": "USER_CREATED"})
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "Criou registro demo")
        detail_response = self.client.get(reverse("configuracoes:audit-detail", args=(event.pk,)))
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "Dados tecnicos")
        self.assertContains(detail_response, "visible")
        self.assertNotContains(detail_response, "Excluir")

    def test_audit_csv_exports_filtered_rows_and_records_one_export_event(self):
        AuditService.record(user=self.admin, category="ADMINISTRATION", action="USER_CREATED", result="SUCCESS", module="Usuários", description="Conta de teste", object_label="alvo")
        response = self.client.get(reverse("configuracoes:audit"), {"category": "ADMINISTRATION", "export": "csv"})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8-sig")
        self.assertIn("Conta de teste", content)
        self.assertNotIn("AUDIT_EXPORT", content)
        export_event = AuditEvent.objects.get(action="AUDIT_EXPORT")
        self.assertEqual(export_event.result, "SUCCESS")
        self.assertEqual(export_event.metadata["format"], "csv")


class AuthenticationAuditTests(TestCase):
    def test_success_failure_and_logout_signals_record_authentication_events(self):
        user = get_user_model().objects.create_user(username="signal-user", password="Secure!Password2026")
        response = self.client.post(reverse("autenticacao:login"), {"username": user.username, "password": "wrong"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(AuditEvent.objects.filter(action="LOGIN_FAILED", user__isnull=True).exists())
        response = self.client.post(reverse("autenticacao:login"), {"username": user.username, "password": "Secure!Password2026"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(AuditEvent.objects.filter(action="LOGIN_SUCCESS", user=user).exists())
        response = self.client.post(reverse("autenticacao:logout"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(AuditEvent.objects.filter(action="LOGOUT", user=user).exists())
