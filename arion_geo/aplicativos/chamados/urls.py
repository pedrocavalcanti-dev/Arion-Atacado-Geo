from django.urls import path

from . import views

app_name = "chamados"

urlpatterns = [
    path("", views.index, name="index"),
    path("api/<int:external_id>/", views.detail, name="detail"),
    path("api/<int:external_id>/tracking/", views.tracking_update, name="tracking_update"),
    path("api/<int:external_id>/notes/", views.note_create, name="note_create"),
    path("views/action/", views.queue_view_action, name="queue_view_action"),
]
