# Fontes de Dados e Escopo

> **Governança:** OTRS e CMDB são as fontes oficiais em seus domínios. O banco ARION é mirror sincronizado, cache operacional e camada analítica, não registro técnico concorrente.

## Matriz de origem

| Informação | Fonte oficial | Mirror / dado ARION | Uso |
|---|---|---|---|
| Ticket, fila e status | OTRS | `OTRSTicket` | Chamados, Dashboard, Cockpit, Mapa e Rankings. |
| Relação Ticket–CI | OTRS `link_relation` | `OTRSTicketConfigItem` | Links associados a ticket. |
| Link / ConfigItem | CMDB | `CMDBLinkMirror` | Base e dimensões analíticas. |
| Provider/ISP | CMDB classe Operadoras | `CMDBOperatorMirror` | Nome de Provider e dados seguros do catálogo. |
| Cliente/Projeto | Nome CMDB + regras ARION | Campos raw e derivados em Link mirror | Semântica derivada com origem/confiança. |
| Acompanhamento NOC | ARION | `TicketTracking`, notes/events | Status local, responsável, notas e histórico. |
| Usuários e permissões | Django local | auth tables + `GroupDataScope` | Autenticação, RBAC e Data Scope. |
| Auditoria | ARION | `AuditEvent` | Eventos relevantes. |
| Views salvas | ARION | `SavedAnalyticsView`, `TicketQueueView` | Preferências do usuário. |

## Fluxo e freshness

Worker lê OTRS via MySQL read-only e CMDB via GenericInterface, valida o resultado e reconcilia os mirrors. Requests web consultam apenas banco local. Se a origem remota falha, o último snapshot permanece disponível, mas fica progressivamente stale. Worker, cadências e cursores em [Worker](WORKER-E-SINCRONIZACAO.md).

## Status e universos

Estados normalizados: OPEN, PENDING, SCHEDULED, RESOLVED, CLOSED, CANCELED e UNKNOWN. Backlog atual é OPEN + PENDING + SCHEDULED no universo/fila da análise; em Cancelamentos/Geral, tickets ativos sem classificação de etapa também ficam visíveis como UNKNOWN para reconciliação. Universo geral válido para performance pode incluir RESOLVED e CLOSED; CANCELED/UNKNOWN não entram nesse universo de performance. Volume por período usa `source_created_at`; análises de término operacional usam `resolved_at`, com `terminal_state_at` apenas como fallback se a resolução estiver ausente. O snapshot atual de backlog não é histórico por si só. O Cockpit reconstrói uma série histórica somente quando o mirror oferece datas de criação e término suficientes e a série reconcilia com o estoque atual; não materializa ciclos completos de reabertura ou transições históricas de fila. O estado bruto `CLOSED` continua preservado.

KPIs gerais contam tickets distintos. O mesmo ticket pode aparecer em cada Link relacionado em agregação por Link. Com Data Scope CUSTOM, ticket sem relação confirmável com Link autorizado não é exposto.

## Dados derivados

`CodigoFechamento` vira `closing_code_raw` e é agrupado por `ClosingReasonCanonicalizer`, sem apagar valor raw. `FalhaMassiva`, `Falha Massiva` e `Defeito Massivo` são aliases de “Falha Massiva”. Procedência é informativa; não prova culpa de Provider nem altera por si só Ranking V2.

Provider/ISP vem da entidade CMDB relacionada. Cliente/Projeto são derivados do nome original por `LinkBusinessIdentityService`, com fonte/confiança. `legacy_project` é classificação histórica e fallback restrito, não fonte oficial atualizada pelo sync. XLSX legado não alimenta as páginas operacionais atuais. ARI Preview mantém dados locais e não faz parte do mirror.

## Data Scope e proteção

Escopo é aplicado no backend antes de filtro, aggregate, paginação, detalhe e export. CUSTOM exige interseção de dimensões; valor ausente ou lista vazia não amplia acesso. Superuser é global.

Senhas de portal não são persistidas nem mostradas. Cliente OTRS não consulta senha de usuário, tokens, artigos ou corpos de mensagens. Secrets de integração não aparecem em response, logs ou auditoria.

## Estudos

Schema e snapshots numéricos em `docs/estudos/` são históricos e associados às datas de estudo; não usar como contagens permanentes nem como contrato vigente do código.
