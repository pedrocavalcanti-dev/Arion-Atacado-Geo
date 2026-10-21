from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.shortcuts import render
from django.templatetags.static import static

from aplicativos.painel.views import STATE_NAMES


@login_required
def index(request):
    flags = {code: static(f"imagens/bandeiras/estados/{code.lower()}.svg") for code in STATE_NAMES}
    return render(request, "mapa/index.html", {"mapbox_token": settings.MAPBOX_PUBLIC_TOKEN, "state_flags": flags})
