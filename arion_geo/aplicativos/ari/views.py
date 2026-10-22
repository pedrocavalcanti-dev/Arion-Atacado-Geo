import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from aplicativos.configuracoes.permissions import access_required

from .models import AriArtifact, AriAttachment, AriConversation
from .services import AriConversationService


def _json_body(request):
    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _message_payload(message):
    return {
        "id": message.pk,
        "role": message.role,
        "content": message.content,
        "message_type": message.message_type,
        "metadata": message.metadata,
        "attachments": [
            {"id": str(item.pk), "name": item.original_name, "size": item.size,
             "mime_type": item.mime_type,
             "download_url": reverse("ari:attachment-download", kwargs={"attachment_id": item.pk})}
            for item in message.attachments.all()
        ],
        "created_at": timezone.localtime(message.created_at).isoformat(),
    }


def _conversation_payload(conversation):
    return {"id": str(conversation.pk), "title": conversation.title}


@login_required
@access_required("view_ari")
def index(request, conversation_id=None):
    conversations = AriConversationService.for_user(request.user)
    query = request.GET.get("q", "").strip()[:80]
    if query:
        conversations = conversations.filter(title__icontains=query)

    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    week_start = today - timedelta(days=6)
    grouped = {"Hoje": [], "Ontem": [], "Últimos 7 dias": [], "Mais antigas": []}
    for conversation in conversations:
        date = timezone.localtime(conversation.updated_at).date()
        label = "Hoje" if date == today else "Ontem" if date == yesterday else "Últimos 7 dias" if date >= week_start else "Mais antigas"
        grouped[label].append(conversation)

    groups = [{"label": label, "items": items} for label, items in grouped.items() if items]
    active = None
    if conversation_id:
        active = get_object_or_404(AriConversationService.for_user(request.user), pk=conversation_id)

    first_name = request.user.first_name.strip() or request.user.get_username()
    initial_messages = [_message_payload(message) for message in active.messages.prefetch_related("attachments")] if active else []
    return render(request, "ari/index.html", {
        "conversation_groups": groups,
        "active_conversation": active,
        "active_messages": active.messages.prefetch_related("attachments") if active else (),
        "initial_messages": initial_messages,
        "search_query": query,
        "first_name": first_name,
        "max_attachment_mb": max(1, int(settings.ARI_MAX_ATTACHMENT_BYTES / (1024 * 1024))),
    })


@login_required
@access_required("view_ari")
@require_GET
def conversation_detail(request, conversation_id):
    conversation = get_object_or_404(
        AriConversationService.for_user(request.user).prefetch_related("messages__attachments"), pk=conversation_id
    )
    return JsonResponse({
        "conversation": _conversation_payload(conversation),
        "messages": [_message_payload(message) for message in conversation.messages.all()],
    })


@login_required
@access_required("view_ari")
@require_POST
def create_message(request, conversation_id=None):
    if request.content_type == "application/json":
        payload = _json_body(request)
        if payload is None:
            return JsonResponse({"error": "Solicitação inválida."}, status=400)
        content = payload.get("content", "")
    else:
        content = request.POST.get("content", "")
    try:
        conversation = AriConversationService.send_message(
            user=request.user,
            content=content,
            conversation_id=conversation_id,
            uploads=request.FILES.getlist("files"),
        )
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)
    return JsonResponse({
        "conversation": _conversation_payload(conversation),
        "messages": [_message_payload(message) for message in conversation.messages.prefetch_related("attachments")],
        "page_url": reverse("ari:conversation", kwargs={"conversation_id": conversation.pk}),
    })


@login_required
@access_required("view_ari")
@require_POST
def rename_conversation(request, conversation_id):
    payload = _json_body(request)
    if payload is None:
        return JsonResponse({"error": "Solicitação inválida."}, status=400)
    try:
        conversation = AriConversationService.rename(
            user=request.user, conversation_id=conversation_id, title=payload.get("title", "")
        )
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)
    return JsonResponse({"conversation": _conversation_payload(conversation)})


@login_required
@access_required("view_ari")
@require_POST
def delete_conversation(request, conversation_id):
    AriConversationService.delete(user=request.user, conversation_id=conversation_id)
    return JsonResponse({"ok": True})


@login_required
@access_required("view_ari")
@require_GET
def attachment_download(request, attachment_id):
    attachment = get_object_or_404(
        AriAttachment.objects.select_related("conversation"),
        pk=attachment_id,
        conversation__user=request.user,
    )
    response = FileResponse(
        attachment.file.open("rb"),
        as_attachment=True,
        filename=attachment.original_name,
        content_type="application/octet-stream",
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    response["Referrer-Policy"] = "no-referrer"
    return response


@login_required
@access_required("view_ari")
@require_GET
def artifact_view(request, artifact_id):
    artifact = get_object_or_404(
        AriArtifact.objects.select_related("conversation"),
        pk=artifact_id,
        conversation__user=request.user,
    )
    template = "ari/artifact_report.html" if artifact.artifact_type == AriArtifact.Type.REPORT_HTML else "ari/artifact_dashboard.html"
    response = render(request, template, {"artifact": artifact, "generated_at": timezone.localtime(artifact.created_at)})
    response["Content-Security-Policy"] = "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:; form-action 'none'; base-uri 'none'; frame-ancestors 'none'"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Frame-Options"] = "DENY"
    response["Referrer-Policy"] = "no-referrer"
    response["Cache-Control"] = "private, no-store"
    if request.GET.get("download") == "1":
        slug = "relatorio-demonstrativo" if artifact.artifact_type == AriArtifact.Type.REPORT_HTML else "dashboard-demo"
        filename = f"ari-{slug}-{timezone.localdate():%Y-%m-%d}.html"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
