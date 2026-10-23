from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from aplicativos.configuracoes.models import GroupDataScope


class MirrorArchitectureTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="mirror-architecture", password="safe-password-1")
        group = Group.objects.get(name="Analista NOC")
        user.groups.set([group])
        scope, _ = GroupDataScope.objects.get_or_create(group=group)
        scope.mode = GroupDataScope.Mode.ALL
        scope.save()
        self.client.force_login(user)

    def test_operational_pages_do_not_open_external_clients_or_read_xlsx_models(self):
        with patch("aplicativos.integracoes.views._cmdb_client", side_effect=AssertionError("CMDB HTTP from request")), patch("aplicativos.integracoes.views._otrs_client", side_effect=AssertionError("OTRS query from request")):
            for url in (reverse("base_links:index"), reverse("dashboard"), reverse("cockpit"), reverse("mapa:index"), reverse("rankings:index")):
                with self.subTest(url=url):
                    self.assertEqual(self.client.get(url).status_code, 200)

        root = Path(__file__).resolve().parents[1]
        files = (
            root / "base_links" / "views.py", root / "painel" / "views.py",
            root / "painel" / "services" / "analytics.py", root / "mapa" / "views.py",
            root / "rankings" / "views.py", root / "rankings" / "services.py",
        )
        forbidden = ("CMDBImport", "ExcelCMDBProvider", "sync_items(", "DemoProviderPerformanceSource", "CMDBLink.objects")
        for source_file in files:
            source = source_file.read_text(encoding="utf-8")
            for marker in forbidden:
                with self.subTest(file=source_file.name, marker=marker):
                    self.assertNotIn(marker, source)
