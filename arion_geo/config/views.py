from .errors import handler403, handler404, handler500


def permission_denied(request, exception=None):
    return handler403(request, exception)


def page_not_found(request, exception=None):
    return handler404(request, exception)


def server_error(request):
    return handler500(request)
