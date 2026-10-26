from types import SimpleNamespace

from django.middleware.security import SecurityMiddleware
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from .errors import csrf_failure
from .middleware import ProductionSecurityHeadersMiddleware, RequestErrorMiddleware


class ProductionSecurityHeadersTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(
        ARION_CSP_REPORT_ONLY=True,
        CONTENT_SECURITY_POLICY_REPORT_ONLY="default-src 'self'; frame-ancestors 'none'",
        PERMISSIONS_POLICY="camera=(), microphone=()",
        DEBUG=False,
    )
    def test_rebuilt_api_error_keeps_private_cache_and_browser_security_headers(self):
        def failing_view(_request):
            return HttpResponse("traceback and internal path", status=500)

        middleware = ProductionSecurityHeadersMiddleware(RequestErrorMiddleware(failing_view))
        response = middleware(self.factory.get("/api/private/"))

        self.assertEqual(response.status_code, 500)
        self.assertNotContains(response, "traceback", status_code=500)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["Permissions-Policy"], "camera=(), microphone=()")
        self.assertFalse(response.has_header("Content-Security-Policy-Report-Only"))

        html_response = middleware(self.factory.get("/dashboard/"))
        self.assertEqual(html_response.status_code, 500)
        self.assertNotContains(html_response, "traceback", status_code=500)
        self.assertEqual(html_response["Content-Security-Policy-Report-Only"], "default-src 'self'; frame-ancestors 'none'")

    def test_all_dynamic_responses_are_private_but_static_files_keep_storage_cache_policy(self):
        dynamic = ProductionSecurityHeadersMiddleware(lambda _request: HttpResponse("private"))
        dynamic_request = self.factory.get("/dashboard/")
        dynamic_request.user = SimpleNamespace(is_authenticated=True)
        self.assertEqual(dynamic(dynamic_request)["Cache-Control"], "private, no-store")

        static = ProductionSecurityHeadersMiddleware(lambda _request: HttpResponse("asset"))
        static_response = static(self.factory.get("/static/arion_build/app.js"))
        self.assertFalse(static_response.has_header("Cache-Control"))

    @override_settings(
        SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
        SECURE_SSL_REDIRECT=True,
        SECURE_HSTS_SECONDS=3600,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=False,
        SECURE_HSTS_PRELOAD=False,
    )
    def test_cloudflare_https_forwarded_proto_avoids_redirect_loop_and_emits_gradual_hsts(self):
        middleware = SecurityMiddleware(lambda _request: HttpResponse("ok"))

        insecure = middleware(self.factory.get("/login/"))
        self.assertEqual(insecure.status_code, 301)
        self.assertTrue(insecure["Location"].startswith("https://"))

        forwarded_https = middleware(self.factory.get("/login/", HTTP_X_FORWARDED_PROTO="https"))
        self.assertEqual(forwarded_https.status_code, 200)
        self.assertEqual(forwarded_https["Strict-Transport-Security"], "max-age=3600")

    def test_csrf_logs_do_not_include_untrusted_origin_or_reason_text(self):
        request = self.factory.post("/login/")
        untrusted_reason = "Origin checking failed - https://operator:secret-value@example.invalid/?token=hidden"

        with self.assertLogs("config.errors", level="WARNING") as captured:
            response = csrf_failure(request, reason=untrusted_reason)

        self.assertEqual(response.status_code, 403)
        self.assertNotIn("secret-value", " ".join(captured.output))
        self.assertNotIn("hidden", " ".join(captured.output))
