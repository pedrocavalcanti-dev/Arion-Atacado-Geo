import json
from pathlib import Path

from django.conf import settings
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
        self.assertContains(response, "data/demo/base.json")
        self.assertContains(response, "data/demo/history.json")
        self.assertNotContains(response, "mapbox-gl-js/v3.33.0/mapbox-gl.js")

    @override_settings(MAPBOX_PUBLIC_TOKEN="pk.test-token")
    def test_configured_public_token_is_exposed_to_map_template(self):
        response = self.client.get(reverse("mapa:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-token="pk.test-token"')
        self.assertContains(response, "mapbox-gl-js/v3.33.0/mapbox-gl.js")
    def test_map_exposes_project_and_period_filters_without_timeline(self):
        response = self.client.get(reverse("mapa:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-project-filter")
        self.assertContains(response, "data-period-filter")
        self.assertContains(response, "data-map-context")
        self.assertNotContains(response, "data-timeline-play")
        self.assertNotContains(response, "data-timeline-months")
        self.assertContains(response, "js/mapa/mapa-data.js")

    def test_demo_history_periods_and_aggregates_are_consistent(self):
        data_dir = Path(settings.BASE_DIR) / "static" / "data" / "demo"
        base = json.loads((data_dir / "base.json").read_text(encoding="utf-8"))
        history = json.loads((data_dir / "history.json").read_text(encoding="utf-8"))
        self.assertEqual(len(history["periods"]), 10)
        self.assertEqual(history["periods"][0]["id"], "2026-01")
        self.assertEqual(history["periods"][-1]["id"], "2026-10")
        self.assertTrue(base["records"])
        for row in history["records"]:
            self.assertGreaterEqual(row["links"], 0)
            self.assertLessEqual(row["recurrences"], row["tickets"])
            self.assertEqual(sum(row["reasons"].values()), row["tickets"])
        for uf in {row["uf"] for row in base["records"]}:
            by_operator = {operator: sum(row["links"] for row in base["records"] if row["uf"] == uf and row["operator"] == operator) for operator in base["operators"]}
            self.assertGreater(sum(by_operator.values()), 0)
