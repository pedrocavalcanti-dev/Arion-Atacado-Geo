import json
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from aplicativos.configuracoes.models import UserDataScope
from .models import AriArtifact, AriAttachment, AriConversation, AriMessage
from .services import AriSimulationService


class AriAccessTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="ari-owner", first_name="Pedro", password="Senha-segura-123"
        )
        self.user.groups.clear()
        permission = Permission.objects.get(
            content_type=ContentType.objects.get_for_model(UserDataScope), codename="view_ari"
        )
        self.user.user_permissions.add(permission)
        self.client.force_login(self.user)

    def post_json(self, url, data):
        return self.client.post(url, data=json.dumps(data), content_type="application/json")

    def test_login_permission_and_navigation(self):
        self.client.logout()
        response = self.client.get(reverse("ari:index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("autenticacao:login"), response["Location"])

        self.client.force_login(self.user)
        response = self.client.get(reverse("ari:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Olá, Pedro.")
        self.assertContains(response, "Preview")
        self.assertContains(response, reverse("ari:index"))
        self.assertContains(response, "ARI I.A")

    def test_permission_is_required(self):
        self.user.user_permissions.clear()
        response = self.client.get(reverse("ari:index"))
        self.assertEqual(response.status_code, 403)

    def test_superuser_keeps_global_access(self):
        root = get_user_model().objects.create_superuser(username="ari-root", password="Senha-segura-123")
        self.client.force_login(root)
        self.assertEqual(self.client.get(reverse("ari:index")).status_code, 200)

    def test_create_send_and_open_history(self):
        response = self.post_json(reverse("ari:create-message"), {"content": "Quais links temos?"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        conversation = AriConversation.objects.get(pk=payload["conversation"]["id"])
        self.assertEqual(conversation.user, self.user)
        self.assertEqual(conversation.title, "Quais links temos")
        self.assertEqual(conversation.messages.count(), 2)
        self.assertEqual(conversation.messages.get(role=AriMessage.Role.USER).content, "Quais links temos?")
        assistant_message = conversation.messages.get(role=AriMessage.Role.ASSISTANT)
        self.assertEqual(assistant_message.message_type, "summary")
        self.assertIn("demo_label", assistant_message.metadata)

        detail = self.client.get(reverse("ari:conversation-detail", kwargs={"conversation_id": conversation.pk}))
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(len(detail.json()["messages"]), 2)
        page = self.client.get(reverse("ari:conversation", kwargs={"conversation_id": conversation.pk}))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Quais links temos")

        response = self.post_json(
            reverse("ari:send-message", kwargs={"conversation_id": conversation.pk}), {"content": "E os chamados?"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(conversation.messages.count(), 4)
        self.assertEqual(response.json()["messages"][-1]["message_type"], "summary")
        self.assertIn("OTRS", response.json()["messages"][-1]["metadata"]["sources"])

    def test_history_search_filters_titles_for_current_user(self):
        AriConversation.objects.create(user=self.user, title="Plano da operadora")
        other = get_user_model().objects.create_user(username="ari-other", password="Senha-segura-123")
        AriConversation.objects.create(user=other, title="Plano confidencial")
        response = self.client.get(reverse("ari:index"), {"q": "operadora"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Plano da operadora")
        self.assertNotContains(response, "Plano confidencial")

    def test_rename_delete_and_invalid_payload(self):
        conversation = AriConversation.objects.create(user=self.user, title="Original")
        response = self.post_json(reverse("ari:rename", kwargs={"conversation_id": conversation.pk}), {"title": "Novo título"})
        self.assertEqual(response.status_code, 200)
        conversation.refresh_from_db()
        self.assertEqual(conversation.title, "Novo título")

        response = self.post_json(reverse("ari:rename", kwargs={"conversation_id": conversation.pk}), {"title": "  "})
        self.assertEqual(response.status_code, 400)
        response = self.post_json(reverse("ari:send-message", kwargs={"conversation_id": conversation.pk}), {"content": ""})
        self.assertEqual(response.status_code, 400)

        response = self.post_json(reverse("ari:delete", kwargs={"conversation_id": conversation.pk}), {})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(AriConversation.objects.filter(pk=conversation.pk).exists())

    def test_foreign_conversations_are_not_accessible_or_mutable(self):
        owner = get_user_model().objects.create_user(username="ari-private-owner", password="Senha-segura-123")
        conversation = AriConversation.objects.create(user=owner, title="Privada")
        detail_url = reverse("ari:conversation-detail", kwargs={"conversation_id": conversation.pk})
        page_url = reverse("ari:conversation", kwargs={"conversation_id": conversation.pk})
        self.assertEqual(self.client.get(detail_url).status_code, 404)
        self.assertEqual(self.client.get(page_url).status_code, 404)
        self.assertEqual(self.post_json(reverse("ari:send-message", kwargs={"conversation_id": conversation.pk}), {"content": "invasão"}).status_code, 404)
        self.assertEqual(self.post_json(reverse("ari:rename", kwargs={"conversation_id": conversation.pk}), {"title": "Invadida"}).status_code, 404)
        self.assertEqual(self.post_json(reverse("ari:delete", kwargs={"conversation_id": conversation.pk}), {}).status_code, 404)
        self.assertFalse(conversation.messages.exists())

    def test_invalid_uuid_is_not_found(self):
        response = self.client.get("/ari/c/not-a-uuid/")
        self.assertEqual(response.status_code, 404)

    def test_preview_response_catalog_is_structured_and_deterministic(self):
        cases = {
            "Resuma a operação": "summary",
            "Compare FIERCE e outro ISP": "comparison",
            "Telefones da FIERCE": "table",
            "Criar plano de ação": "action_plan",
            "Alerta abaixo da meta": "alert",
            "Estamos na meta?": "goal",
            "Gere um relatório": "report",
            "Crie um dashboard": "dashboard",
        }
        for prompt, expected in cases.items():
            with self.subTest(prompt=prompt):
                response = AriSimulationService.respond(prompt)
                self.assertEqual(response["type"], expected)
                if expected != "text":
                    self.assertIn("demo_label", response["metadata"])
        table = AriSimulationService.respond("Telefones da FIERCE")
        self.assertEqual(len(table["metadata"]["rows"]), 3)
        self.assertIn("dados reais", table["content"])
        self.assertEqual(AriSimulationService.respond("resuma a operação"), AriSimulationService.respond("resuma a operação"))

    def test_upload_validation_storage_download_and_delete_cleanup(self):
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            upload = SimpleUploadedFile("operacao.csv", b"equipe,status\nNOC,ok\n", content_type="text/csv")
            response = self.client.post(reverse("ari:create-message"), {"content": "", "files": [upload]})
            self.assertEqual(response.status_code, 200, response.content)
            conversation = AriConversation.objects.get(pk=response.json()["conversation"]["id"])
            attachment = AriAttachment.objects.get()
            self.assertEqual(attachment.conversation, conversation)
            self.assertTrue(Path(attachment.file.path).is_file())
            assistant = conversation.messages.get(role=AriMessage.Role.ASSISTANT)
            self.assertEqual(assistant.message_type, "file_received")
            self.assertEqual(assistant.message_type, "file_received")
            self.assertIn("analisei", assistant.content)
            self.assertIn("Preview", assistant.content)

            download_url = reverse("ari:attachment-download", kwargs={"attachment_id": attachment.pk})
            downloaded = self.client.get(download_url)
            self.assertEqual(downloaded.status_code, 200)
            self.assertEqual(downloaded["Content-Type"], "application/octet-stream")
            self.assertEqual(downloaded["X-Content-Type-Options"], "nosniff")
            self.assertIn("attachment;", downloaded["Content-Disposition"])
            self.assertEqual(b"".join(downloaded.streaming_content), b"equipe,status\nNOC,ok\n")

            stored_path = Path(attachment.file.path)
            attachment.delete()
            self.assertFalse(stored_path.exists())

    def test_upload_rejects_extension_mime_signature_and_size(self):
        cases = [
            SimpleUploadedFile("payload.html", b"<script>alert(1)</script>", content_type="text/html"),
            SimpleUploadedFile("forged.pdf", b"not a pdf", content_type="application/pdf"),
            SimpleUploadedFile("wrong.csv", b"x,y\n1,2\n", content_type="image/png"),
        ]
        for upload in cases:
            with self.subTest(filename=upload.name):
                response = self.client.post(reverse("ari:create-message"), {"content": "arquivo", "files": [upload]})
                self.assertEqual(response.status_code, 400)
                self.assertFalse(AriConversation.objects.exists())
        with override_settings(ARI_MAX_ATTACHMENT_BYTES=4):
            too_large = SimpleUploadedFile("large.txt", b"12345", content_type="text/plain")
            response = self.client.post(reverse("ari:create-message"), {"content": "arquivo", "files": [too_large]})
        self.assertEqual(response.status_code, 400)

    def test_attachment_and_artifact_are_private_and_artifact_is_controlled(self):
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            upload = SimpleUploadedFile("dados.txt", b"texto de exemplo", content_type="text/plain")
            response = self.client.post(reverse("ari:create-message"), {"content": "", "files": [upload]})
            attachment = AriAttachment.objects.get()
            other = get_user_model().objects.create_user(username="ari-outsider", password="Senha-segura-123")
            self.client.force_login(other)
            self.assertEqual(self.client.get(reverse("ari:attachment-download", kwargs={"attachment_id": attachment.pk})).status_code, 404)

            self.client.force_login(self.user)
            response = self.post_json(reverse("ari:create-message"), {"content": "Gere um relatório da operação"})
            self.assertEqual(response.status_code, 200)
            payload = response.json()["messages"][-1]
            artifact = AriArtifact.objects.get()
            self.assertEqual(payload["message_type"], "report")
            artifact_url = payload["metadata"]["artifact_url"]
            artifact_response = self.client.get(artifact_url)
            self.assertEqual(artifact_response.status_code, 200)
            self.assertIn("sandbox", artifact_response["Content-Security-Policy"])
            self.assertContains(artifact_response, "Dados demonstrativos")
            self.assertContains(artifact_response, "Resumo executivo")
            self.assertNotContains(artifact_response, "<script")
            downloaded_artifact = self.client.get(f"{artifact_url}?download=1")
            self.assertEqual(downloaded_artifact.status_code, 200)
            self.assertIn("attachment;", downloaded_artifact["Content-Disposition"])
            self.assertTrue(downloaded_artifact["Content-Disposition"].endswith('.html"'))
            self.client.force_login(other)
            self.assertEqual(self.client.get(artifact_url).status_code, 404)
            self.client.force_login(self.user)
            report_conversation = AriConversation.objects.get(pk=response.json()["conversation"]["id"])
            report_conversation.delete()
            self.assertFalse(AriArtifact.objects.filter(pk=artifact.pk).exists())
            attachment_conversation = attachment.conversation
            attachment_conversation.delete()
            self.assertFalse(AriAttachment.objects.filter(pk=attachment.pk).exists())

    def test_dashboard_artifact_is_generated_with_demo_content(self):
        response = self.post_json(reverse("ari:create-message"), {"content": "Crie um mini dashboard"})
        payload = response.json()["messages"][-1]
        self.assertEqual(payload["message_type"], "dashboard")
        artifact = AriArtifact.objects.get()
        page = self.client.get(payload["metadata"]["artifact_url"])
        self.assertEqual(page.status_code, 200)
        for label in ("Chamados", "SLA", "Reincidências", "Links", "Distribuição", "DADOS DEMONSTRATIVOS"):
            self.assertContains(page, label)
        self.assertIn("default-src 'none'", page["Content-Security-Policy"])
