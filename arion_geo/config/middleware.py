"""Request correlation and API error response normalization."""

import secrets
import logging

from django.conf import settings
from django.shortcuts import resolve_url

from .errors import _safe_user_id, error_response, html_error, is_api_request


STATUS_CODES = {
    400: "BAD_REQUEST",
    401: "AUTHENTICATION_REQUIRED",
    403: "ACCESS_DENIED",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    408: "REQUEST_TIMEOUT",
    409: "CONFLICT",
    413: "FILE_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
    502: "INTEGRATION_UNAVAILABLE",
    503: "INTEGRATION_UNAVAILABLE",
    504: "INTEGRATION_TIMEOUT",
}
logger = logging.getLogger("config.errors")


class RequestErrorMiddleware:
    """Attach a non-secret request reference and standardize API failures."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = f"REQ-{secrets.token_hex(8).upper()}"
        response = self.get_response(request)
        return self.process_response(request, response)

    def process_response(self, request, response):
        if not getattr(response, "_arion_error_response", False):
            status = response.status_code
            api_request = is_api_request(request)
            is_login_redirect = False
            if api_request and status in (301, 302, 303, 307, 308):
                login_path = resolve_url(settings.LOGIN_URL).rstrip("/")
                destination = response.get("Location", "").split("?", 1)[0].rstrip("/")
                is_login_redirect = destination == login_path
            if is_login_redirect:
                response = error_response(request, "AUTHENTICATION_REQUIRED")
            elif settings.DEBUG and not api_request and status >= 500:
                # Keep Django's technical HTML page available for local debugging.
                pass
            elif status == 405 or (api_request and status >= 400) or (not api_request and status >= 400 and status != 400):
                headers = {}
                for name in ("Allow", "Retry-After"):
                    if response.has_header(name):
                        headers[name] = response[name]
                code = STATUS_CODES.get(status, "INTERNAL_ERROR" if status >= 500 else "BAD_REQUEST")
                if status >= 500:
                    logger.error(
                        "HTTP error response status=%s request_id=%s user_id=%s method=%s path=%s",
                        status, request.request_id, _safe_user_id(request), request.method, request.path_info,
                    )
                response = error_response(request, code, status=status, headers=headers) if api_request else html_error(request, code, status=status, headers=headers)

        response["X-Request-ID"] = request.request_id
        return response
