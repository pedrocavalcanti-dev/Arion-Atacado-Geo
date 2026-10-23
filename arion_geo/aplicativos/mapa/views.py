from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.templatetags.static import static

from aplicativos.configuracoes.permissions import access_required
from aplicativos.integracoes.services.analytics import LinkQueryService

from aplicativos.painel.views import STATE_NAMES


@login_required
@access_required("view_map")
def index(request):
    links = LinkQueryService.base(request.user)
    flags = {code: static(f"imagens/bandeiras/estados/{code.lower()}.svg") for code in STATE_NAMES}
    return render(request, "mapa/index.html", {
        "mapbox_token": settings.MAPBOX_PUBLIC_TOKEN,
        "state_flags": flags,
        "link_count": links.count(),
    })
