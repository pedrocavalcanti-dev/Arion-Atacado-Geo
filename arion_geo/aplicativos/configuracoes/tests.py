import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from .models import UserPreference
from .access_control import GROUP_ANALYST, GROUP_MANAGER, GROUP_SYSTEM_ADMIN, is_system_admin
from .models import UserDataScope
from aplicativos.base_links.models import CMDBLink, Operadora, Projeto, Provider


class UserPreferenceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="theme-user", password="Senha-segura-123")
        self.get_url = reverse("preferences_api:preferences")
        self.theme_url = reverse("preferences_api:theme")

    def test_user_without_preference_receives_default_dark(self):
        self.client.force_login(self.user)
        response = self.client.get(self.get_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"theme": "dark"})
        self.assertEqual(UserPreference.objects.get(user=self.user).theme, "dark")

    def test_get_returns_stored_preference(self):
        UserPreference.objects.create(user=self.user, theme=UserPreference.Theme.LIGHT)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.get_url).json(), {"theme": "light"})

    def test_authenticated_user_can_set_light_and_dark_and_preference_persists(self):
        self.client.force_login(self.user)
        for theme in ("light", "dark"):
            response = self.client.post(self.theme_url, data=json.dumps({"theme": theme}), content_type="application/json")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"theme": theme})
            self.assertEqual(UserPreference.objects.get(user=self.user).theme, theme)

    def test_invalid_theme_returns_bad_request(self):
        self.client.force_login(self.user)
        response = self.client.post(self.theme_url, data=json.dumps({"theme": "blue"}), content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_unauthenticated_user_cannot_read_or_change_preferences(self):
        self.assertEqual(self.client.get(self.get_url).status_code, 302)
        response = self.client.post(self.theme_url, data=json.dumps({"theme": "light"}), content_type="application/json")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(UserPreference.objects.exists())

    def test_authenticated_template_receives_saved_theme(self):
        UserPreference.objects.create(user=self.user, theme=UserPreference.Theme.LIGHT)
        self.client.force_login(self.user)
        response = self.client.get(reverse("painel:index"))
        self.assertContains(response, 'data-user-theme="light"')

    def test_theme_update_requires_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        response = csrf_client.post(self.theme_url, data=json.dumps({"theme": "light"}), content_type="application/json")
        self.assertEqual(response.status_code, 403)


class AccountSettingsTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="account-user", password="Senha-segura-123", first_name="Ana", last_name="Silva", email="ana@example.com")
        self.other = user_model.objects.create_user(username="other-user", password="Senha-segura-123", first_name="Bia", email="bia@example.com")

    def test_settings_pages_require_login(self):
        for name in ("index", "account", "security", "appearance"):
            response = self.client.get(reverse(f"configuracoes:{name}"))
            self.assertEqual(response.status_code, 302)
            self.assertIn("/login/", response.url)

    def test_authenticated_shared_header_routes_render_without_reverse_errors(self):
        self.client.force_login(self.user)
        route_names = (
            "painel:index",
            "dashboard",
            "cockpit",
            "mapa:index",
            "rankings:index",
            "base_links:index",
            "configuracoes:index",
            "configuracoes:account",
            "configuracoes:security",
            "configuracoes:appearance",
        )
        for route_name in route_names:
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Minha conta")
                self.assertContains(response, "Configurações")

    def test_user_menu_separates_account_and_settings_destinations(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("painel:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{reverse("configuracoes:account")}"')
        self.assertContains(response, f'href="{reverse("configuracoes:index")}"')
        self.assertNotEqual(reverse("configuracoes:account"), reverse("configuracoes:index"))

    def test_settings_landing_shows_only_allowed_shortcuts_and_all_links_resolve(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("configuracoes:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gerencie sua conta, preferências e recursos administrativos disponíveis.")
        for label in ("Minha conta", "Segurança", "Aparência"):
            self.assertContains(response, label)
        self.assertNotContains(response, "ADMINISTRAÇÃO")
        self.assertNotContains(response, "Grupos e acessos")
        for route in ("account", "security", "appearance"):
            self.assertContains(response, f'href="{reverse(f"configuracoes:{route}")}"')

    def test_account_shows_only_signed_in_user_profile(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("configuracoes:account"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ana@example.com")
        self.assertContains(response, "account-user")
        self.assertNotContains(response, "bia@example.com")

    def test_profile_update_changes_only_current_user_allowed_fields(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("configuracoes:account"), {
            "first_name": "Ana Maria",
            "last_name": "Santos",
            "email": "ana.maria@example.com",
            "user_id": self.other.pk,
            "is_staff": "on",
            "username": "changed-user",
        })
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.other.refresh_from_db()
        self.assertEqual((self.user.first_name, self.user.last_name, self.user.email), ("Ana Maria", "Santos", "ana.maria@example.com"))
        self.assertEqual(self.user.username, "account-user")
        self.assertFalse(self.user.is_staff)
        self.assertEqual((self.other.first_name, self.other.email), ("Bia", "bia@example.com"))

    def test_password_change_keeps_current_session_authenticated(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("configuracoes:security"), {
            "old_password": "Senha-segura-123",
            "new_password1": "Outra-senha-segura-456",
            "new_password2": "Outra-senha-segura-456",
        })
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Outra-senha-segura-456"))
        self.assertEqual(self.client.get(reverse("configuracoes:account")).status_code, 200)

    def test_appearance_uses_and_updates_existing_user_preference(self):
        self.client.force_login(self.user)
        UserPreference.objects.create(user=self.user, theme=UserPreference.Theme.DARK)
        response = self.client.get(reverse("configuracoes:appearance"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-theme-option="light"')
        self.assertContains(response, 'data-theme-option="dark"')
        update = self.client.post(reverse("preferences_api:theme"), data=json.dumps({"theme": "light"}), content_type="application/json")
        self.assertEqual(update.status_code, 200)
        self.assertEqual(UserPreference.objects.get(user=self.user).theme, UserPreference.Theme.LIGHT)


class AccessControlTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.admin = self.User.objects.create_user(username="access-admin", password="Senha-segura-123")
        self.admin.groups.set([Group.objects.get(name=GROUP_SYSTEM_ADMIN)])
        self.analyst = self.User.objects.create_user(username="access-analyst", password="Senha-segura-123")

    def test_system_admin_sees_administration_shortcuts_on_settings_landing(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("configuracoes:index"))
        self.assertEqual(response.status_code, 200)
        for route, label in (("users", "Usuários"), ("groups", "Grupos e acessos"), ("scopes", "Escopos de dados"),
                             ("audit", "Auditoria"), ("integrations", "Integrações"), ("system", "Sistema")):
            with self.subTest(route=route):
                self.assertContains(response, f'href="{reverse(f"configuracoes:{route}")}"')
                self.assertContains(response, label)

    def test_system_admin_can_open_administration_pages(self):
        self.client.force_login(self.admin)
        for name in ("users", "groups", "scopes", "audit", "integrations", "system"):
            with self.subTest(route=name):
                response = self.client.get(reverse(f"configuracoes:{name}"))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "ADMINISTRAÇÃO")

    def test_analyst_has_no_administration_navigation_and_gets_403(self):
        self.client.force_login(self.analyst)
        response = self.client.get(reverse("configuracoes:account"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(reverse("ari:index")).status_code, 200)
        self.assertNotContains(response, "ADMINISTRAÇÃO")
        for name in ("users", "groups", "scopes", "audit", "integrations", "system"):
            with self.subTest(route=name):
                response = self.client.get(reverse(f"configuracoes:{name}"))
                self.assertEqual(response.status_code, 403)

    def test_manager_profile_has_module_access_but_no_administration(self):
        self.analyst.groups.set([Group.objects.get(name=GROUP_MANAGER)])
        self.client.force_login(self.analyst)
        self.assertEqual(self.client.get(reverse("cockpit")).status_code, 200)
        self.assertEqual(self.client.get(reverse("ari:index")).status_code, 200)
        self.assertEqual(self.client.get(reverse("configuracoes:users")).status_code, 403)

    def test_auditor_can_view_audit_but_not_other_administrative_areas(self):
        auditor = Group.objects.get(name="Consulta / Auditoria")
        self.analyst.groups.set([auditor])
        self.client.force_login(self.analyst)
        self.assertEqual(self.client.get(reverse("configuracoes:audit")).status_code, 200)
        self.assertEqual(self.client.get(reverse("ari:index")).status_code, 200)
        for name in ("users", "groups", "scopes", "integrations", "system"):
            with self.subTest(route=name):
                self.assertEqual(self.client.get(reverse(f"configuracoes:{name}")).status_code, 403)

    def test_bootstrap_is_idempotent_and_restores_access_for_unassigned_users(self):
        self.analyst.groups.clear()
        call_command("bootstrap_access", verbosity=0)
        call_command("bootstrap_access", verbosity=0)
        self.analyst.refresh_from_db()
        self.assertEqual(self.analyst.groups.filter(name=GROUP_ANALYST).count(), 1)
        self.assertEqual(Group.objects.filter(name__in=(GROUP_SYSTEM_ADMIN, GROUP_MANAGER, GROUP_ANALYST, "Consulta / Auditoria")).count(), 4)

    def test_admin_can_create_user_with_django_validated_initial_password(self):
        self.client.force_login(self.admin)
        analyst_group = Group.objects.get(name=GROUP_ANALYST)
        response = self.client.post(reverse("configuracoes:user-create"), {
            "username": "new-operator", "first_name": "Nina", "last_name": "Costa", "email": "nina@example.com",
            "password1": "XyZ!2026_SenhaForte", "password2": "XyZ!2026_SenhaForte",
            "groups": [analyst_group.pk], "scope_mode": "all",
        })
        self.assertEqual(response.status_code, 302)
        created = self.User.objects.get(username="new-operator")
        self.assertTrue(created.check_password("XyZ!2026_SenhaForte"))
        self.assertEqual(list(created.groups.all()), [analyst_group])
        self.assertEqual(created.data_scope.mode, UserDataScope.Mode.ALL)

    def test_group_permissions_are_presented_with_friendly_module_labels(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("configuracoes:group-create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Administração")
        self.assertContains(response, "Gerenciar usuários")
        self.assertNotContains(response, "configuracoes.manage_users")

    def test_system_admin_permission_set_cannot_be_removed_from_last_admin_group(self):
        self.client.force_login(self.admin)
        group = Group.objects.get(name=GROUP_SYSTEM_ADMIN)
        permission = Permission.objects.get(content_type__app_label="configuracoes", codename="view_dashboard")
        response = self.client.post(reverse("configuracoes:group-edit", args=(group.pk,)), {"name": group.name, "permissions": [permission.pk]})
        self.assertEqual(response.status_code, 200)
        group.refresh_from_db()
        self.assertTrue(group.permissions.filter(codename="manage_users").exists())
        self.assertContains(response, "último perfil de sistema ativo")

    def test_last_active_system_administrator_cannot_be_deactivated(self):
        self.assertTrue(is_system_admin(self.admin))
        self.client.force_login(self.admin)
        response = self.client.post(reverse("configuracoes:user-edit", args=(self.admin.pk,)), {
            "first_name": "", "last_name": "", "email": "", "is_active": "",
            "groups": [Group.objects.get(name=GROUP_ANALYST).pk], "scope_mode": "all",
        })
        self.assertEqual(response.status_code, 200)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.assertContains(response, "último Administrador do Sistema")


class DataScopeIntegrationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="scope-claro", password="Senha-segura-123")
        self.client.force_login(self.user)
        self.claro = Operadora.objects.create(name="Claro", normalized_name="claro")
        self.vivo = Operadora.objects.create(name="Vivo", normalized_name="vivo")
        self.bradesco = Projeto.objects.create(name="Bradesco", normalized_name="bradesco")
        self.fust = Projeto.objects.create(name="FUST", normalized_name="fust")
        self.claro_provider = Provider.objects.create(name="ISP Claro", normalized_name="isp-claro")
        self.vivo_provider = Provider.objects.create(name="ISP Vivo", normalized_name="isp-vivo")
        CMDBLink.objects.create(config_item_id="scope-1", uf="SP", operadora=self.claro, projeto=self.bradesco, provider=self.claro_provider)
        CMDBLink.objects.create(config_item_id="scope-2", uf="RJ", operadora=self.claro, projeto=self.fust, provider=self.claro_provider)
        CMDBLink.objects.create(config_item_id="scope-3", uf="MG", operadora=self.vivo, projeto=self.bradesco, provider=self.vivo_provider)
        self.scope, _ = UserDataScope.objects.get_or_create(user=self.user)
        self.scope.mode = UserDataScope.Mode.CUSTOM
        self.scope.save()
        self.scope.allowed_operators.set([self.claro])
        self.scope.allowed_projects.set([self.bradesco])

    def test_scope_is_operator_and_project_intersection_in_base_dashboard_and_rankings(self):
        base = self.client.get(reverse("base_links:index"))
        self.assertEqual(base.status_code, 200)
        self.assertEqual(base.context["page_obj"].paginator.count, 1)
        self.assertEqual(list(base.context["operators"]), [self.claro])
        self.assertEqual(list(base.context["projects"]), [self.bradesco])
        outside_detail = self.client.get(reverse("base_links:detail", args=(CMDBLink.objects.get(config_item_id="scope-3").pk,)))
        self.assertEqual(outside_detail.status_code, 404)
        dashboard = self.client.get(reverse("dashboard"))
        self.assertEqual(dashboard.context["total_links"], 1)
        self.assertEqual(dashboard.context["top_providers"][0]["provider__name"], "ISP Claro")
        ranking = self.client.get(reverse("rankings:index"))
        self.assertEqual([row["name"] for row in ranking.context["providers"]], ["ISP Claro"])

    def test_scope_is_applied_before_cockpit_filters_and_options(self):
        response = self.client.post(reverse("analytics-query"), data=json.dumps({"metric": "links", "group_by": "operator", "period": "2026-10", "filters": {}}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["value"], 1)
        self.assertEqual(response.json()["options"]["operator"], ["Claro"])
        outside = self.client.post(reverse("analytics-query"), data=json.dumps({"metric": "links", "group_by": "operator", "period": "2026-10", "filters": {"operator": "Vivo"}}), content_type="application/json")
        self.assertEqual(outside.status_code, 200)
        self.assertEqual(outside.json()["value"], 0)

    def test_scope_is_applied_before_map_aggregation_and_filtering(self):
        all_data = self.client.get(reverse("base_links:map-aggregates"))
        self.assertEqual(all_data.status_code, 200)
        self.assertEqual(all_data.json()["total_links"], 1)
        self.assertEqual([row["name"] for row in all_data.json()["operators"]], ["Claro"])
        outside = self.client.get(reverse("base_links:map-aggregates"), {"operator": self.vivo.pk})
        self.assertEqual(outside.status_code, 200)
        self.assertEqual(outside.json()["total_links"], 0)
