import unicodedata

from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.urls import reverse

from .file_security import validate_upload
from .models import AriArtifact, AriAttachment, AriConversation, AriMessage


class AriSimulationService:
    """Deterministic preview responses; this service never contacts data or AI providers."""

    INTENT_CATALOG = (
        ("provider_phones", ("telefone fierce", "telefones fierce", "comparativo dos telefones")),
        ("demo_analysis", ("demonstracao de analise", "exemplo demonstrativo de analise", "analisar arquivo")),
        ("dashboard", ("dashboard", "painel de indicadores")),
        ("report", ("relatorio", "gere um relatorio", "gerar relatorio")),
        ("action_plan", ("plano de acao", "crie um plano", "criar plano")),
        ("comparison", ("compare", "comparativo", "comparar", " vs ", "contra ")),
        ("alert", ("alerta", "abaixo da meta", "risco operacional")),
        ("goal", ("meta", "em relacao a meta", "atingimos a meta")),
        ("summary", ("resuma", "resumo", "como esta a operacao", "indicadores da operacao")),
    )

    @staticmethod
    def _normalize(prompt):
        normalized = unicodedata.normalize("NFKD", prompt.casefold())
        return "".join(char for char in normalized if not unicodedata.combining(char))

    @classmethod
    def detect_intent(cls, prompt):
        normalized = cls._normalize(prompt)
        if "fierce" in normalized and any(word in normalized for word in ("telefone", "fone")):
            return "provider_phones"
        for intent, patterns in cls.INTENT_CATALOG:
            if any(pattern in normalized for pattern in patterns):
                return intent
        if any(word in normalized for word in ("chamado", "otrs", "link", "circuito")):
            return "summary"
        return "generic"

    @classmethod
    def respond(cls, prompt, *, attachment_names=()):
        if attachment_names:
            names = ", ".join(f'"{name}"' for name in attachment_names)
            return {
                "type": "file_received",
                "content": f"Recebi {names}. Nesta versão Preview, não analisei o conteúdo. A demonstração abaixo usa um cenário fictício e não é derivada do arquivo enviado.",
                "metadata": {"demo_label": "Arquivo recebido · sem análise real", "next_actions": [
                    {"label": "Ver demonstração de análise", "prompt": "Ver exemplo demonstrativo de análise"},
                ], "sources": "CMDB · OTRS · Arion", "sources_status": "Não conectadas à ARI"},
            }

        intent = cls.detect_intent(prompt)
        demo = {"demo_label": "Dados demonstrativos · valores fictícios", "sources": "CMDB · OTRS · Arion", "sources_status": "Não conectadas à ARI"}
        if intent == "provider_phones":
            return {
                "type": "table",
                "content": "Ainda não tenho acesso aos dados reais da FIERCE. Esta tabela demonstra como a consulta poderá ser apresentada no futuro.",
                "metadata": {**demo, "title": "Comparativo FIERCE", "columns": ["Unidade", "Telefone", "Status", "Observação"], "rows": [
                    ["Unidade A", "(11) 0000-0001", "Ativo", "Principal"],
                    ["Unidade B", "(11) 0000-0002", "Ativo", "Backup"],
                    ["Unidade C", "(11) 0000-0003", "Indisponível", "Verificar cadastro"],
                ]},
            }
        if intent == "comparison":
            return {
                "type": "comparison", "content": "Comparativo demonstrativo entre FIERCE e ISP B.",
                "metadata": {**demo, "left_label": "FIERCE", "right_label": "ISP B", "metrics": [
                    {"label": "Chamados", "left": 18, "right": 11, "suffix": ""},
                    {"label": "SLA", "left": 91, "right": 96, "suffix": "%"},
                    {"label": "Reincidências", "left": 3, "right": 1, "suffix": ""},
                ], "insights": ["FIERCE apresenta maior volume no exemplo.", "O SLA demonstrativo está 5 p.p. abaixo do ISP B.", "A reincidência demonstrativa também está maior."],
                    "next_actions": [{"label": "Criar plano de ação para FIERCE", "prompt": "Criar plano de ação para FIERCE"}]},
            }
        if intent == "action_plan":
            return {
                "type": "action_plan", "content": "Plano de ação demonstrativo para reduzir reincidências.",
                "metadata": {**demo, "objective": "Reduzir reincidências da operação", "priority": "Alta", "actions": [
                    "Revisar links com reincidência.", "Identificar ISP com maior concentração.", "Validar a causa raiz.",
                    "Criar acompanhamento semanal.", "Revisar o resultado após 30 dias.",
                ], "owner": "Equipe NOC", "deadline": "30 dias"},
            }
        if intent == "alert":
            return {
                "type": "alert", "content": "Alerta operacional demonstrativo.",
                "metadata": {**demo, "level": "attention", "title": "SLA abaixo da meta", "current": "92%", "target": "95%", "impact": "3 p.p. abaixo da meta.", "suggestion": "Revisar chamados fora do SLA e os principais ISPs envolvidos."},
            }
        if intent == "goal":
            return {
                "type": "goal", "content": "Acompanhamento de meta no cenário demonstrativo.",
                "metadata": {**demo, "title": "Meta de SLA", "current": 92, "target": 95, "difference": "-3 p.p.", "status": "Abaixo da meta"},
            }
        if intent == "summary":
            return {
                "type": "summary", "content": "Resumo da operação no cenário demonstrativo.",
                "metadata": {**demo, "kpis": [
                    {"label": "Chamados", "value": "52"}, {"label": "Abertos", "value": "32"},
                    {"label": "SLA", "value": "92%"}, {"label": "Reincidentes", "value": "3"},
                ], "insights": ["SLA abaixo da meta fictícia de 95%.", "Reincidências concentradas em 2 ISPs.", "Volume superior ao período anterior."],
                    "next_actions": [{"label": "Criar plano de ação", "prompt": "Criar plano de ação para a operação"}]},
            }
        if intent == "report":
            return {
                "type": "report", "content": "Preparei um relatório demonstrativo com dados fictícios.",
                "metadata": {**demo, "artifact_title": "Relatório operacional demonstrativo", "sections": [
                    "Resumo executivo", "Indicadores", "Principais desvios", "Riscos", "Plano de ação", "Próximos passos",
                ]},
            }
        if intent == "dashboard":
            return {
                "type": "dashboard", "content": "Criei um mini dashboard demonstrativo usando valores fictícios. Ele não substitui o Dashboard oficial do Arion.",
                "metadata": {**demo, "artifact_title": "Dashboard demonstrativo", "kpis": [
                    {"label": "Chamados", "value": "52"}, {"label": "SLA", "value": "92%"},
                    {"label": "Reincidências", "value": "3"}, {"label": "Links", "value": "342"},
                ]},
            }
        if intent == "demo_analysis":
            return {
                "type": "summary", "content": "Este exemplo visual usa dados fictícios pré-definidos e não foi calculado a partir do arquivo.",
                "metadata": {**demo, "kpis": [
                    {"label": "Registros de exemplo", "value": "128"}, {"label": "Itens em atenção", "value": "7"},
                    {"label": "SLA demonstrativo", "value": "94%"},
                ], "insights": ["Exemplo de classificação de registros.", "Nenhum conteúdo do arquivo foi interpretado."]},
            }
        return {
            "type": "text",
            "content": "Ainda estou em modo demonstração. Quando as integrações operacionais e a inteligência estiverem ativas, poderei consultar os dados do Arion para responder com precisão.",
            "metadata": {"demo_label": "Preview · fontes não conectadas", "sources": "CMDB · OTRS · Arion", "sources_status": "Não conectadas à ARI", "next_actions": [
                {"label": "Resumir operação", "prompt": "Resuma a operação"},
                {"label": "Criar plano de ação", "prompt": "Criar plano de ação"},
                {"label": "Comparar provedores", "prompt": "Compare FIERCE e outro ISP"},
                {"label": "Gerar relatório", "prompt": "Gere um relatório da operação"},
            ]},
        }


class AriConversationService:
    """User-scoped persistence for preview conversations and their simulated exchanges."""

    @staticmethod
    def for_user(user):
        return AriConversation.objects.filter(user=user)

    @staticmethod
    def title_from_prompt(prompt):
        title = " ".join(prompt.split()).strip(" .?!\t\n\r")
        return title[:77].rstrip() + "…" if len(title) > 80 else title[:80]

    @classmethod
    def send_message(cls, *, user, content, conversation_id=None, uploads=()):
        try:
            validated_uploads = [validate_upload(upload) for upload in uploads]
        except ValidationError as error:
            raise ValueError(" ".join(error.messages)) from error
        prompt = " ".join(str(content or "").split()).strip()
        if not prompt and not validated_uploads:
            raise ValueError("Digite uma mensagem para continuar.")
        if validated_uploads and not prompt:
            prompt = "Enviei arquivo(s) para demonstração."
        if len(prompt) > 4000:
            raise ValueError("A mensagem deve ter no máximo 4.000 caracteres.")
        stored_files = []
        try:
            with transaction.atomic():
                if conversation_id is None:
                    conversation = AriConversation.objects.create(user=user)
                else:
                    conversation = get_object_or_404(cls.for_user(user), pk=conversation_id)

                is_first_message = not conversation.messages.exists()
                user_message = AriMessage.objects.create(conversation=conversation, role=AriMessage.Role.USER, content=prompt)
                for validated in validated_uploads:
                    attachment = AriAttachment(conversation=conversation, message=user_message,
                                               original_name=validated.original_name,
                                               mime_type=validated.mime_type, size=validated.size)
                    attachment.file.save(validated.original_name, validated.upload, save=False)
                    stored_files.append((attachment.file.storage, attachment.file.name))
                    attachment.save()

                response = AriSimulationService.respond(
                    prompt, attachment_names=[item.original_name for item in validated_uploads]
                )
                reply = AriMessage.objects.create(
                    conversation=conversation, role=AriMessage.Role.ASSISTANT, content=response["content"],
                    message_type=response["type"], metadata=response["metadata"],
                )
                artifact_kind = {"report": AriArtifact.Type.REPORT_HTML, "dashboard": AriArtifact.Type.DASHBOARD_HTML}.get(response["type"])
                if artifact_kind:
                    artifact_title = "Relatório operacional demonstrativo" if artifact_kind == AriArtifact.Type.REPORT_HTML else "Dashboard demonstrativo"
                    artifact = AriArtifact.objects.create(
                        conversation=conversation, message=reply, artifact_type=artifact_kind, title=artifact_title
                    )
                    metadata = dict(reply.metadata)
                    metadata.update({
                        "artifact_title": artifact.title,
                        "artifact_url": reverse("ari:artifact", kwargs={"artifact_id": artifact.pk}),
                        "download_url": reverse("ari:artifact", kwargs={"artifact_id": artifact.pk}) + "?download=1",
                    })
                    reply.metadata = metadata
                    reply.save(update_fields=("metadata",))
                if is_first_message:
                    conversation.title = cls.title_from_prompt(prompt) or "Nova conversa"
                conversation.save(update_fields=("title", "updated_at"))
                return conversation
        except Exception:
            for storage, name in stored_files:
                storage.delete(name)
            raise

    @classmethod
    def rename(cls, *, user, conversation_id, title):
        title = " ".join(str(title or "").split()).strip()
        if not title or len(title) > 80:
            raise ValueError("O título deve ter entre 1 e 80 caracteres.")
        conversation = get_object_or_404(cls.for_user(user), pk=conversation_id)
        conversation.title = title
        conversation.save(update_fields=("title", "updated_at"))
        return conversation

    @classmethod
    def delete(cls, *, user, conversation_id):
        conversation = get_object_or_404(cls.for_user(user), pk=conversation_id)
        conversation.delete()
