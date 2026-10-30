from django.contrib.auth import get_user_model
from django.test import TestCase
from pathlib import Path
from django.urls import reverse
from django.contrib.auth.models import Group
from aplicativos.configuracoes.models import GroupDataScope


class AuthenticationFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="operador", password="Senha-segura-123")
        group = Group.objects.get(name="Analista NOC")
        self.user.groups.set([group])
        scope, _ = GroupDataScope.objects.get_or_create(group=group)
        scope.mode = GroupDataScope.Mode.ALL
        scope.save()

    def test_root_redirects_to_login_for_anonymous_user(self):
        response = self.client.get(reverse("home"))
        self.assertRedirects(response, reverse("autenticacao:login"))

    def test_root_redirects_to_overview_for_authenticated_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("home"))
        self.assertRedirects(response, reverse("painel:index"))

    def test_login_page_responds(self):
        response = self.client.get(reverse("autenticacao:login"))
        self.assertEqual(response.status_code, 200)
        for text in (
            "ARION OPS", "NOC ATACADO",
            "Acesse sua área de operação.",
            "Conectando grandes empresas a operações que não podem parar.",
            "Uma visão única",
            "Atendimento conectado a grandes operações.",
            "Pedro Cavalcanti",
        ):
            self.assertContains(response, text)
        self.assertEqual(response.content.count(b"data-login-slide data-slide-label"), 3)
        self.assertContains(response, "arion-ops-login-operacao.webp")
        self.assertContains(response, "arion-ops-login-relatorios.webp")
        self.assertContains(response, "data-login-previous")
        self.assertContains(response, "data-login-next")
        self.assertContains(response, "data-login-go-to")
        script = Path("frontend_src/js/autenticacao/login.js").read_text(encoding="utf-8")
        self.assertIn("const autoplayDelay = 7000", script)

    def test_invalid_login_keeps_session_anonymous(self):
        response = self.client.post(
            reverse("autenticacao:login"),
            {"username": "operador", "password": "invalid-password"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_map_and_panel_require_authentication(self):
        for url_name in ("mapa:index", "painel:index"):
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertRedirects(response, f"{reverse('autenticacao:login')}?next={reverse(url_name)}")

    def test_valid_login_redirects_to_overview(self):
        response = self.client.post(reverse("autenticacao:login"), {"username": "operador", "password": "Senha-segura-123"})
        self.assertRedirects(response, reverse("painel:index"))

    def test_logout_ends_session_and_returns_to_login(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("autenticacao:logout"))
        self.assertRedirects(response, reverse("autenticacao:login"))
        self.assertNotIn("_auth_user_id", self.client.session)
