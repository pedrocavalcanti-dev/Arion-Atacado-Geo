from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.shortcuts import render
from django.templatetags.static import static

from aplicativos.painel.views import STATE_NAMES
from aplicativos.base_links.data_source import get_data_source_mode
from aplicativos.configuracoes.permissions import access_required


@login_required
@access_required("view_map")
def index(request):
    flags = {code: static(f"imagens/bandeiras/estados/{code.lower()}.svg") for code in STATE_NAMES}
    return render(request, "mapa/index.html", {"mapbox_token": settings.MAPBOX_PUBLIC_TOKEN, "state_flags": flags, "data_source_mode": get_data_source_mode()})
