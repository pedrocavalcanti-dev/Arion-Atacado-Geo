import json
from pathlib import Path

from django.contrib.staticfiles import finders
from django.template.loader import get_template
from django.test import SimpleTestCase
from django.urls import reverse

from aplicativos.integracoes.services.project_names import canonical_project_name


class PwaDeliveryTests(SimpleTestCase):
    def test_login_shell_links_manifest_and_hides_install_until_the_browser_allows_it(self):
        response = self.client.get("/login/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'rel="manifest" href="/manifest.webmanifest"')
        self.assertContains(response, 'data-pwa-install hidden')
        self.assertContains(response, "apple-mobile-web-app-capable")

    def test_manifest_is_public_with_installable_scope_and_icons(self):
        response = self.client.get(reverse("pwa-manifest"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"].split(";", 1)[0], "application/manifest+json")
        self.assertIn("public", response["Cache-Control"])
        manifest = json.loads(response.content)
        self.assertEqual(manifest["start_url"], "/")
        self.assertEqual(manifest["scope"], "/")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["short_name"], "ARION")
        self.assertIn({"src": "/static/pwa/arion-512-maskable.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}, manifest["icons"])

    def test_worker_has_root_scope_and_is_never_cached(self):
        response = self.client.get(reverse("pwa-service-worker"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("javascript", response["Content-Type"])
        self.assertEqual(response["Service-Worker-Allowed"], "/")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertNotIn(b"__ARION_CACHE_REVISION__", response.content)
        self.assertIn(b"arion-shell-", response.content)
        self.assertIn(b"request.mode === \"navigate\"", response.content)
        self.assertIn(b"url.pathname.startsWith(\"/static/\")", response.content)
        self.assertIn(b"Cache-Control", response.content)

    def test_pwa_icons_are_real_pngs_with_expected_dimensions(self):
        expected = {
            "pwa/arion-192.png": 192,
            "pwa/arion-512.png": 512,
            "pwa/arion-512-maskable.png": 512,
            "pwa/arion-apple-touch-icon.png": 180,
        }
        for relative_path, size in expected.items():
            with self.subTest(icon=relative_path):
                icon_path = Path(finders.find(relative_path))
                contents = icon_path.read_bytes()
                self.assertTrue(contents.startswith(b"\x89PNG\r\n\x1a\n"))
                self.assertGreater(len(contents), 100)
                self.assertEqual((contents[16] << 24) + (contents[17] << 16) + (contents[18] << 8) + contents[19], size)
                self.assertEqual((contents[20] << 24) + (contents[21] << 16) + (contents[22] << 8) + contents[23], size)

    def test_operational_responses_are_never_added_to_the_worker_cache(self):
        worker = Path(finders.find("pwa/service-worker.js")).read_text(encoding="utf-8")
        static_guard = worker.index('if (!url.pathname.startsWith("/static/")')
        cache_write = worker.index("await cache.put(request, response.clone())")
        self.assertLess(static_guard, cache_write)
        self.assertLess(worker.index('if (request.mode === "navigate")'), static_guard)
        self.assertIn("fetch(request).catch", worker)
        self.assertIn("request.method !== \"GET\"", worker)
        self.assertIn('const OFFLINE_URL = "/static/pwa/offline.html"', worker)

    def test_mobile_navigation_is_permission_gated_and_ticket_modal_keeps_header_visible(self):
        template = Path("arion_geo/templates/base.html").read_text(encoding="utf-8")
        navigation = Path("arion_geo/templates/partials/mobile_navigation.html").read_text(encoding="utf-8")
        modal_css = Path("arion_geo/static/css/base-links.css").read_text(encoding="utf-8")

        self.assertIn('include "partials/mobile_navigation.html"', template)
        self.assertIn("data-mobile-navigation", navigation)
        self.assertIn("perms.configuracoes.view_operational_tickets", navigation)
        self.assertIn("perms.configuracoes.manage_groups", navigation)
        self.assertIn("perms.configuracoes.view_integrations", navigation)
        self.assertIn("perms.configuracoes.view_system_info", navigation)
        self.assertIn("{% csrf_token %}", navigation)
        self.assertIn(".base-ticket-dialog[open] { display:flex; flex-direction:column; }", modal_css)
        self.assertIn("position:sticky; top:0", modal_css)
        self.assertIn("overflow-y:auto", modal_css)

    def test_mobile_settings_sections_and_admin_card_templates_are_present(self):
        for template_name in (
            "configuracoes/base.html", "configuracoes/admin/users.html",
            "configuracoes/admin/groups.html", "configuracoes/admin/scopes.html",
            "configuracoes/admin/audit.html", "integracoes/base_integracoes.html",
            "documentacao/base_documentacao.html",
        ):
            get_template(template_name)
        settings = Path("arion_geo/templates/configuracoes/base.html").read_text(encoding="utf-8")
        users = Path("arion_geo/templates/configuracoes/admin/users.html").read_text(encoding="utf-8")
        audit = Path("arion_geo/templates/configuracoes/admin/audit.html").read_text(encoding="utf-8")
        css = Path("arion_geo/static/css/configuracoes/settings.css").read_text(encoding="utf-8")
        self.assertIn('class="settings-mobile-sections"', settings)
        self.assertIn('class="admin-table admin-table--cards"', users)
        self.assertIn('class="admin-table audit-table admin-table--cards"', audit)
        self.assertIn('.settings-mobile-sections nav a[aria-current="page"]', css)
        self.assertIn('.audit-table--cards tr', css)

    def test_map_controls_hide_internal_provenance_and_keep_project_aliases_explicit(self):
        template = Path("arion_geo/templates/mapa/_cmdb.html").read_text(encoding="utf-8")
        script = Path("frontend_src/js/mapa/mapa-real.js").read_text(encoding="utf-8")
        self.assertNotIn("data-provenance-filter", template)
        self.assertNotIn("Procedência", template)
        self.assertNotIn('chips.push(["uf"', script)
        self.assertEqual(canonical_project_name("BDN BRADESCO"), "BRADESCO")
        self.assertEqual(canonical_project_name("PROJETO BB"), "BANCO DO BRASIL")
        self.assertEqual(canonical_project_name("BOTICARIO"), "O BOTICÁRIO")
        self.assertEqual(canonical_project_name("BRADESCO SEGUROS"), "BRADESCO SEGUROS")
        self.assertEqual(canonical_project_name("BB SEGUROS"), "BB SEGUROS")
        self.assertIn('<div class="map-backdrop" data-panel-backdrop aria-hidden="true"></div>', template)
        self.assertNotIn('panelBackdrop.addEventListener("click",clearSelection)', script)
        self.assertNotIn('event.key==="Escape"&&state.selectedUF', script)

    def test_operational_ticket_template_compiles_with_mobile_filter_and_card_layout(self):
        get_template("chamados/index.html")
        template = Path("arion_geo/templates/chamados/index.html").read_text(encoding="utf-8")
        styles = Path("arion_geo/static/css/chamados/chamados.css").read_text(encoding="utf-8")
        self.assertIn('data-mobile-filter-sheet', template)
        self.assertIn('data-mobile-filters-open', template)
        self.assertIn('data-label="Chamado"', template)
        self.assertIn('data-label="Acompanhamento ARION"', template)
        self.assertIn('name="assignee"', template[template.index('class="ticket-filter-secondary"'):])
        self.assertIn(".ticket-mobile-filter-heading { display:none; }", styles)
        self.assertIn(".ticket-more-filters[open] .ticket-filter-secondary { display:grid; }", styles)
        self.assertIn("max-inline-size:none; box-sizing:border-box", styles)
        self.assertIn('data-mobile-filters-close><svg', template)
