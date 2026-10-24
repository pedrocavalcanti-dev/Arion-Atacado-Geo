from django.urls import path

from . import views

app_name = "rankings"
urlpatterns = [path("", views.index, name="index")]
urlpatterns += [path("provedor/<int:provider_id>/", views.provider_detail, name="provider-detail")]
urlpatterns += [path("exportar/<str:file_format>/", views.export, name="export")]
