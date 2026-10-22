from django.urls import path

from . import views

app_name = "ari"

urlpatterns = [
    path("", views.index, name="index"),
    path("c/<uuid:conversation_id>/", views.index, name="conversation"),
    path("api/conversations/", views.create_message, name="create-message"),
    path("api/conversations/<uuid:conversation_id>/", views.conversation_detail, name="conversation-detail"),
    path("api/conversations/<uuid:conversation_id>/messages/", views.create_message, name="send-message"),
    path("api/conversations/<uuid:conversation_id>/rename/", views.rename_conversation, name="rename"),
    path("api/conversations/<uuid:conversation_id>/delete/", views.delete_conversation, name="delete"),
    path("attachments/<uuid:attachment_id>/download/", views.attachment_download, name="attachment-download"),
    path("artifacts/<uuid:artifact_id>/", views.artifact_view, name="artifact"),
]
