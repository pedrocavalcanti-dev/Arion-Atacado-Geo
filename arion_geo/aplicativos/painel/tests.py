from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from aplicativos.painel.views import STATE_NAMES


class DashboardAndFlagsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="noc-exec", password="Senha-segura-123")
        self.client.force_login(self.user)

    def test_all_27_state_flags_exist_locally_as_svg(self):
        flags_dir = Path(settings.BASE_DIR) / "static" / "imagens" / "bandeiras" / "estados"
        self.assertEqual(len(STATE_NAMES), 27)
        for code in STATE_NAMES:
            path = flags_dir / f"{code.lower()}.svg"
            self.assertTrue(path.is_file(), f"Bandeira ausente: {path.name}")
            self.assertGreater(path.stat().st_size, 150)

    def test_dashboard_renders_kpis_percentages_and_state_flags(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-count="7200"')
        self.assertContains(response, 'data-count="603"')
        self.assertContains(response, 'data-count="133"')
        self.assertContains(response, "22,1%")
        self.assertContains(response, "imagens/bandeiras/estados/sp.svg")
        self.assertContains(response, 'alt="Bandeira de São Paulo"')
