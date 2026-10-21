import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from .models import UserPreference


@login_required
@require_GET
def preferences(request):
    preference, _ = UserPreference.objects.get_or_create(user=request.user)
    return JsonResponse({"theme": preference.theme})


@login_required
@require_POST
def update_theme(request):
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Corpo JSON inválido."}, status=400)
    if not isinstance(payload, dict) or payload.get("theme") not in UserPreference.Theme.values:
        return JsonResponse({"error": "Tema inválido. Use 'dark' ou 'light'."}, status=400)

    preference, _ = UserPreference.objects.get_or_create(user=request.user)
    preference.theme = payload["theme"]
    preference.save(update_fields=("theme", "updated_at"))
    return JsonResponse({"theme": preference.theme})
