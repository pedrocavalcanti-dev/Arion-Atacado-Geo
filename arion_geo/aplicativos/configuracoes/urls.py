from django.urls import path

from . import views

app_name = "configuracoes"

urlpatterns = [
    path("", views.preferences, name="preferences"),
    path("theme/", views.update_theme, name="theme"),
]
