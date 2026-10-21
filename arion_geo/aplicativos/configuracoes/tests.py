import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import UserPreference


class UserPreferenceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="theme-user", password="Senha-segura-123")
        self.get_url = reverse("configuracoes:preferences")
        self.theme_url = reverse("configuracoes:theme")

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
