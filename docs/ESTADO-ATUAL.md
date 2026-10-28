# Estado atual do ARION ATACADO GEO

Revisão do workspace em 28/10/2026. A matriz descreve capacidades encontradas no código, sem publicar contagens voláteis de uma base específica.

## Matriz de módulos

| Módulo | Estado | Fonte | Escrita | Observação |
|---|---|---|---|---|
| Dashboard | Ativo | `CMDBLinkMirror`, `OTRSTicket`, relações e queries locais | Sem escrita CMDB/OTRS | KPIs atuais e séries por criação têm recortes diferentes. |
| Chamados | Ativo | Tickets atuais da fila NOC + `TicketTracking` | Acompanhamento apenas no ARION | OTRS read-only. |
| Cockpit | Ativo | Mirrors OTRS/CMDB | `SavedAnalyticsView` local; export de leitura | Data Scope no backend. |
| Mapa | Ativo | Mirrors e relações Ticket-ConfigItem | Sem edição da fonte | Agrega por UF; não geocodifica. |
| Rankings | Ativo (V2) | Chamados válidos e Links associados | Export de leitura | Índice operacional, não SLA nem causalidade de Provider. |
| Base | Ativo | `CMDBLinkMirror`, `CMDBOperatorMirror` | Consulta/exportação | Importador XLSX legado não é fluxo normal. |
| ARI | Preview | Models locais de conversas e artifacts | Dados locais de conversa/anexo | Não há integração LLM ativa confirmada. |
| CMDB Mirror | Ativo no código | ServiceUp Search/Get | Escrita no banco ARION | Sincronizado por processo separado. |
| OTRS Mirror | Ativo no código | MySQL OTRS somente leitura | Escrita no banco ARION | FAST incremental e FULL reconciliador. |
| Worker | Ativo no código | `integration_worker` | Atualiza mirrors/estado | Requer processo ativo para freshness. |
| RBAC/Data Scope | Ativo | Django Groups/Permissions e `GroupDataScope` | Administração protegida | Superuser técnico é global. |
| Auditoria | Ativo | `AuditEvent` via `AuditService` | Histórico local | Metadata sanitizada; não é debug log. |
| Central documental | Ativo | Markdown versionado em `docs/` | Leitura | Acesso protegido por `configuracoes.manage_groups`. |

## Banco e fontes

A seleção suporta SQLite e MySQL. O processo consultado neste workspace estava usando MySQL; isso varia conforme ambiente e configuração de startup. Não publicar nome de schema, host, usuário, senha nem connection string. Consulte [Banco de Dados](BANCO-DE-DADOS.md) para precedência e fallback.

A preparação de produção V1 inclui modo Django explícito, Waitress localhost, supervisor Windows para Web/Worker, build de assets production, `collectstatic`, production-check, preparação do serviço Cloudflare Tunnel e backup MySQL. Isso descreve código/script disponível; domínio, host novo, MySQL restaurado, conta Cloudflare/Tunnel e credenciais de serviço ainda precisam ser configurados e verificados no ambiente de destino. Consulte [Implantação e Produção](IMPLANTACAO-E-PRODUCAO.md).

OTRS/CMDB são fontes oficiais. `CMDBLinkMirror`, `CMDBOperatorMirror`, `OTRSTicket` e `OTRSTicketConfigItem` são cópias locais. `TicketTracking` representa trabalho interno do ARION.

## Frontend mobile e PWA

O frontend Django usa navegação dedicada em tablet/mobile e adaptações por módulo; a Fila apresenta Tickets como cartões em telas estreitas. O PWA possui manifest, ícones derivados do favicon, instalação Chromium/iOS, modo standalone e aviso de atualização sob ação do usuário. O Service Worker não armazena conteúdo operacional autenticado: páginas e APIs seguem para rede e o modo offline mostra apenas indisponibilidade. Build de produção/`collectstatic` e validação em dispositivos no servidor continuam necessários antes de publicar.

## Não anunciar como implementado

- Escrita de status, nota, artigo ou atribuição no OTRS.
- SLA cumprido sem regra/dados validados.
- Geocodificação de endereços ou coordenadas precisas por instalação.
- Integração LLM ativa em ARI Preview.
- Importação XLSX como ingestão operacional normal.
- Apps `projetos`, `relatorios` e `importacoes` como instalados em `INSTALLED_APPS`.

Estudos em `docs/estudos/` são snapshots históricos e têm data própria. A página de estado é referência atual, não changelog. Se o worker parar, a web pode continuar lendo o último snapshot, cuja idade deve ser monitorada.
