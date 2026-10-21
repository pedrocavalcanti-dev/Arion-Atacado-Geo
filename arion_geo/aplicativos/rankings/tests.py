from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .services import get_providers


class RankingsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="rankings-user", password="Senha-segura-123")

    def test_rankings_requires_authentication(self):
        response = self.client.get(reverse("rankings:index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_rankings_renders_demo_summary_and_table_controls(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("rankings:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ranking global dos provedores")
        self.assertContains(response, "Ranking de provedores")
        self.assertContains(response, "Base total monitorada")
        self.assertContains(response, "Links ativos")
        self.assertContains(response, "Dados demonstrativos")
        self.assertContains(response, "Melhor SLA")
        self.assertContains(response, "Mais links")
        self.assertContains(response, "data-ranking-rows")
        self.assertContains(response, "NexaLink Telecom")

    def test_demo_dataset_is_consistent_and_score_ordered(self):
        providers = get_providers()
        self.assertEqual(len(providers), 20)
        self.assertEqual(sum(row["links"] for row in providers), 7200)
        for row in providers:
            self.assertGreater(row["links"], 0)
            self.assertEqual(row["dentro_sla"] + row["fora_sla"], row["chamados"])
            self.assertLessEqual(row["estourados"], row["fora_sla"])
            self.assertGreaterEqual(row["score"], 0)
            self.assertLessEqual(row["score"], 100)
