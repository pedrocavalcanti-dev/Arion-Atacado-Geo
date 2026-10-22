from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .services import get_providers
from .performance import DemoProviderPerformanceSource
from aplicativos.base_links.models import CMDBLink, Operadora, Projeto, Provider


class RankingsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="rankings-user", password="Senha-segura-123")

    def test_rankings_requires_authentication(self):
        response = self.client.get(reverse("rankings:index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_rankings_renders_real_providers_and_demo_summary(self):
        provider = Provider.objects.create(name="ISP CMDB real", normalized_name="isp cmdb real")
        CMDBLink.objects.create(config_item_id="rank-1", provider=provider, uf="SP")
        self.client.force_login(self.user)
        response = self.client.get(reverse("rankings:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ranking global dos provedores")
        self.assertContains(response, "Ranking de provedores")
        self.assertContains(response, "Base total CMDB")
        self.assertContains(response, "Links ativos")
        self.assertContains(response, "Demonstração")
        self.assertContains(response, "Melhor SLA")
        self.assertContains(response, "Mais links")
        self.assertContains(response, "data-ranking-rows")
        self.assertContains(response, "ISP CMDB real")
        self.assertNotContains(response, "NexaLink Telecom")
        row = response.context["providers"][0]
        self.assertEqual(row["links"], 1)
        self.assertEqual(row["share"], round(1 / 1 * 100, 1))

    def test_more_links_ranking_orders_real_link_counts(self):
        first = Provider.objects.create(name="ISP 1", normalized_name="isp 1")
        second = Provider.objects.create(name="ISP 2", normalized_name="isp 2")
        for index in range(3):
            CMDBLink.objects.create(config_item_id=f"a-{index}", provider=first)
        CMDBLink.objects.create(config_item_id="b-1", provider=second)
        self.client.force_login(self.user)
        response = self.client.get(reverse("rankings:index"), {"sort": "links"})
        self.assertEqual(response.context["providers"][0]["id"], first.pk)
        self.assertEqual(response.context["providers"][0]["links"], 3)

    def test_invalid_provider_names_are_excluded(self):
        invalid = Provider.objects.create(name="N/A", normalized_name="n/a")
        CMDBLink.objects.create(config_item_id="invalid-1", provider=invalid)
        self.client.force_login(self.user)
        response = self.client.get(reverse("rankings:index"))
        self.assertEqual(response.context["providers"], [])

    def test_performance_source_is_deterministic_by_provider_and_period(self):
        source = DemoProviderPerformanceSource()
        self.assertEqual(source.get(42, 267), source.get(42, 267))
        metrics = source.get(42, 267)
        self.assertEqual(metrics["dentro_sla"] + metrics["fora_sla"], metrics["chamados"])
        self.assertLessEqual(metrics["reincidencias"], metrics["chamados"])
        self.assertLessEqual(metrics["estourados"], metrics["fora_sla"])

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
