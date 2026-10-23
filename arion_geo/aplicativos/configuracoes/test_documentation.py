from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from .documentation import DOCUMENTS, DocumentationService, render_markdown
from .models import GroupDataScope, UserPreference


class DocumentationPortalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user(username="docs-admin", password="secret")
        content_type = ContentType.objects.get_for_model(GroupDataScope)
        permission = Permission.objects.get(content_type=content_type, codename="manage_groups")
        cls.admin.user_permissions.add(permission)
        cls.regular_user = get_user_model().objects.create_user(username="docs-user", password="secret")

    def test_authorized_user_can_open_portal_and_page(self):
        self.client.force_login(self.admin)
        home = self.client.get(reverse("configuracoes:documentation"))
        page = self.client.get(reverse("configuracoes:documentation-page", kwargs={"slug": "arquitetura"}))
        self.assertEqual(home.status_code, 200)
        self.assertContains(home, "Como podemos ajudar?")
        self.assertContains(home, "Segurança e operação")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Fluxo de dados")

    def test_access_requires_login_and_existing_permission(self):
        url = reverse("configuracoes:documentation")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.regular_user)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_portal_receives_the_existing_saved_theme(self):
        UserPreference.objects.create(user=self.admin, theme=UserPreference.Theme.LIGHT)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("configuracoes:documentation"))
        self.assertContains(response, 'data-user-theme="light"')
        self.assertContains(response, 'data-theme-toggle')

    def test_unknown_and_arbitrary_slugs_are_not_resolved(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("configuracoes:documentation-page", kwargs={"slug": "arquivo-secreto"})).status_code, 404)
        self.assertIsNone(DocumentationService.get(".."))

    def test_path_traversal_mapping_is_rejected(self):
        malicious = dict(DOCUMENTS)
        malicious["fora"] = ("Fora", "", "Padrões", "../settings.py")
        with patch("aplicativos.configuracoes.documentation.DOCUMENTS", malicious):
            self.assertIsNone(DocumentationService.get("fora"))

    def test_renderer_covers_headings_tables_code_quotes_and_links(self):
        body, headings = render_markdown(
            "# Seção Árvore\n## Outro título\n\n| Coluna | Valor |\n| --- | --- |\n| Nome | **ARION** |\n\n> Nota técnica\n\n```python\nprint('ok')\n```\n\n```mermaid\ngraph TD\n```\n\n[Segurança](../SEGURANCA.md)"
        )
        self.assertIn('id="secao-arvore"', body)
        self.assertIn("<thead>", body)
        self.assertIn("<blockquote>", body)
        self.assertIn('class="language-python"', body)
        self.assertIn("Ver código Mermaid", body)
        self.assertIn(reverse("configuracoes:documentation-page", kwargs={"slug": "seguranca"}), body)
        self.assertIn(reverse("configuracoes:documentation") + "#home-docs-modulos", render_markdown("[Funcionalidades](funcionalidades/)")[0])
        self.assertIn(">Arquitetura</a>", render_markdown("[ARQUITETURA.md](../ARQUITETURA.md)")[0])
        self.assertEqual(headings[1][1], "outro-titulo")

    def test_search_finds_document_content(self):
        results = DocumentationService.search("CMDB")
        self.assertTrue(results)
        self.assertTrue(any(result["slug"] == "base" for result in results))

    def test_every_registered_document_renders(self):
        self.client.force_login(self.admin)
        for slug in DOCUMENTS:
            with self.subTest(slug=slug):
                response = self.client.get(reverse("configuracoes:documentation-page", kwargs={"slug": slug}))
                self.assertEqual(response.status_code, 200)

