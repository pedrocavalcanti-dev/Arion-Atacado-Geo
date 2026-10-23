"""Private URLConf used only by error handler tests."""

from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.http import JsonResponse
from django.urls import path
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST


def malformed_request(request):
    raise SuspiciousOperation("private parser detail")


def forbidden(request):
    raise PermissionDenied("private permission codename")


def explode(request):
    raise RuntimeError("SECRET_KEY=private-value; SELECT * FROM internal_table")


@require_POST
def post_only(request):
    return JsonResponse({"ok": True})


@csrf_protect
@require_POST
def csrf_only(request):
    return JsonResponse({"ok": True})


urlpatterns = [
    path("bad-request/", malformed_request),
    path("api/bad-request/", malformed_request),
    path("forbidden/", forbidden),
    path("explode/", explode),
    path("api/explode/", explode),
    path("api/post-only/", post_only),
    path("csrf-only/", csrf_only),
]

handler400 = "config.errors.handler400"
handler403 = "config.errors.handler403"
handler404 = "config.errors.handler404"
handler500 = "config.errors.handler500"
