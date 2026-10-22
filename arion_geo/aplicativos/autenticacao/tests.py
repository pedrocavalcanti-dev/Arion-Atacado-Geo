from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AuthenticationFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="operador", password="Senha-segura-123")

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
        self.assertContains(response, "Inteligência geográfica")

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
