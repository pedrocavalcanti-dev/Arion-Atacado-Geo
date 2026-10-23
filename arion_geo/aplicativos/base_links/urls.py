from django.urls import path

from . import views

app_name = "base_links"

urlpatterns = [
    path("", views.index, name="index"),
    path("provedores/", views.providers, name="providers"),
    path("exportar/", views.export_csv, name="export"),
    path("importar/", views.import_cmdb, name="import"),
    path("importar/confirmar/", views.confirm_import, name="confirm"),
    path("api/mapa/", views.map_aggregates, name="map-aggregates"),
    path("api/provedor/<int:pk>/", views.provider_detail, name="provider-detail"),
    path("api/<int:pk>/", views.detail, name="detail"),
]
