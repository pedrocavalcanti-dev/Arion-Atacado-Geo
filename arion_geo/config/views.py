import hashlib
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET

from .errors import handler403, handler404, handler500


def permission_denied(request, exception=None):
    return handler403(request, exception)


def page_not_found(request, exception=None):
    return handler404(request, exception)


def server_error(request):
    return handler500(request)


@require_GET
def health(request):
    response = JsonResponse({"status": "ok"})
    response["Cache-Control"] = "no-store"
    return response


@require_GET
def pwa_manifest(request):
    """Serve the manifest with a stable root URL and explicit media type."""
    path = finders.find("pwa/manifest.webmanifest")
    if not path:
        return HttpResponse(status=404)
    with open(path, "rb") as manifest_file:
        response = HttpResponse(manifest_file.read(), content_type="application/manifest+json; charset=utf-8")
    response["Cache-Control"] = "public, max-age=300, must-revalidate"
    return response


@require_GET
def pwa_service_worker(request):
    """Serve the worker from / so its scope can include the full application."""
    path = finders.find("pwa/service-worker.js")
    if not path:
        return HttpResponse(status=404)
    response = HttpResponse(_pwa_service_worker_source(path), content_type="application/javascript; charset=utf-8")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


@lru_cache(maxsize=1)
def _pwa_service_worker_source(worker_path):
    """Tie cache names to the frontend build and offline shell without exposing build details."""
    source_path = Path(worker_path)
    source = source_path.read_text(encoding="utf-8")
    digest = hashlib.sha256(source.encode("utf-8"))
    build_manifest = Path(settings.BASE_DIR).parent / "var" / "arion-frontend-manifest.json"
    if build_manifest.is_file():
        digest.update(build_manifest.read_bytes())
    for relative_path in (
        "css/pwa.css",
        "css/pwa-offline.css",
        "pwa/manifest.webmanifest",
        "pwa/offline.html",
        "pwa/arion-mark.svg",
        "pwa/arion-192.png",
        "pwa/arion-512.png",
        "pwa/arion-512-maskable.png",
        "pwa/arion-apple-touch-icon.png",
    ):
        asset_path = finders.find(relative_path)
        if asset_path:
            digest.update(relative_path.encode("utf-8"))
            digest.update(Path(asset_path).read_bytes())
    revision = digest.hexdigest()[:12]
    return source.replace("__ARION_CACHE_REVISION__", revision)
