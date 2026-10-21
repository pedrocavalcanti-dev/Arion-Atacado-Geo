from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


class MapPageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="noc-user", password="Senha-segura-123")
        self.client.force_login(self.user)

    @override_settings(MAPBOX_PUBLIC_TOKEN="")
    def test_map_renders_configuration_and_local_data_without_token(self):
        response = self.client.get(reverse("mapa:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-token=""')
        self.assertContains(response, "geo/brasil_estados.geojson")
        self.assertContains(response, "data/mapa-demo.json")
        self.assertNotContains(response, "mapbox-gl-js/v3.33.0/mapbox-gl.js")

    @override_settings(MAPBOX_PUBLIC_TOKEN="pk.test-token")
    def test_configured_public_token_is_exposed_to_map_template(self):
        response = self.client.get(reverse("mapa:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-token="pk.test-token"')
        self.assertContains(response, "mapbox-gl-js/v3.33.0/mapbox-gl.js")
