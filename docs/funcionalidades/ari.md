# ARI

## Estado implementado

ARI está no estado **Preview**. O app persiste conversas, mensagens, anexos e artifacts locais em `AriConversation`, `AriMessage`, `AriAttachment` e `AriArtifact`. `AriConversationService` coordena conversa; `AriSimulationService` produz comportamento demonstrativo. Não afirmar uso de LLM, API externa ou resposta generativa real sem integração ativa verificável.

## Fluxo e URLs

`/ari/` abre a experiência e `/ari/c/<uuid>/` uma conversa. APIs sob `/ari/api/conversations/` criam/alteram conversas e mensagens; há endpoints de rename/delete, download de attachment e acesso a artifacts definidos em `ari/urls.py` e `ari/views.py`. A autorização isola recursos por ownership/usuário.

O conteúdo de Preview deve estar identificado como demonstrativo e não alimenta Dashboard, Chamados ou analytics. ARI não consulta CMDB/OTRS nem modifica registros oficiais.

## Arquivos e segurança

`file_security.py` centraliza regras de upload/serving. O backend permite até cinco anexos por request, com limite de 20 MiB por arquivo e 40 MiB no total; um upload handler aplica a quota enquanto recebe os bytes. Views validam tipo/nome e conferem pertencimento antes de entregar anexo de storage privado. Ações relevantes passam por auditoria. Não anexar conteúdo sensível real de tickets em Preview nem incluir secrets/PII em artifact demonstrativo.

## Limites

Integração com modelo de IA, ferramentas operacionais e automação com decisão permanece **Planejado / Backlog** enquanto não houver código/configuração ativa. Preview não é automação autônoma nem fonte operacional.
