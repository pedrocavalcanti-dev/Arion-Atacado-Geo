# Banco de dados e espelhos operacionais

As paginas operacionais usam os mirrors do app `integracoes`; as tabelas antigas de Base XLSX permanecem apenas para rollback e historico.

## Cadeia de relacionamento

`OTRSTicket` -> `OTRSTicketConfigItem.config_item_id` (OTRS `link_relation.source_key`) -> `CMDBLinkMirror.source_config_item_id` (CMDB `ConfigItemID`) -> `CMDBLinkMirror.operator` -> `CMDBOperatorMirror`.

`source_number` corresponde ao identificador de negocio `Number`/antigo `ConfigItem#`, mas nao substitui `ConfigItemID` como chave da relacao Ticket-CI. Relacoes sem mirror local preservam `cmdb_link=NULL`; multiplos CIs por ticket sao suportados.

## Modelos

- `CMDBOperatorMirror`: campos seguros de operador e presenca na origem.
- `CMDBLinkMirror`: atributos CMDB, FK opcional de operadora, `legacy_project` transitorio e `is_present_in_source`.
- `OTRSTicket`: fila, estado de negocio, prioridade, servico, SLA por nome, datas de criacao/alteracao e `is_present_in_queue`.
- `OTRSStateMapping`: mapeamento conhecido para `OPEN`, `PENDING`, `RESOLVED`, `CLOSED`, `CANCELED` ou `UNKNOWN`.
- `OTRSTicketConfigItem`: relacao N:N unica por ticket/ConfigItem/tipo, com FK local opcional.
- `IntegrationRun`, `IntegrationSyncState`, `IntegrationLease`: historico sanitizado, freshness/cursor e lock multiprocesso com expiracao.

Campos de senha de CMDB e OTRS nao existem nos mirrors. O cliente MySQL OTRS nao configura conexao ORM externa e opera somente em leitura.

## Aplicacao e reconciliacao

O servico le e valida o snapshot remoto antes da escrita local. Apply e transacional; respostas incompletas/falhas nao marcam registros ausentes. Fast OTRS reconcilia relacoes em lote somente para tickets afetados; full reconcilia a fila e relacoes completas. A ausencia em snapshot completo marca presenca falsa, sem hard delete.

O cursor de OTRS usa `ticket.change_time`, sobreposicao de 2 minutos e so e atualizado apos apply bem-sucedido. Um lease por fonte e persistido no banco e expira apos falta de heartbeat.

## Legacy

`base_links.CMDBImport`, `CMDBLink`, `Provider` e tabelas relacionadas nao foram removidas. Importacao esta desativada na interface operacional. Nenhuma view de Base, Dashboard, Cockpit, Mapa ou Rankings consulta essas tabelas. `project_legacy` foi copiado para compatibilidade temporaria de filtro/escopo; nao e atualizado a partir de arquivo.
## Semantica dos espelhos CMDB

Embora o model/FK legado se chame `CMDBOperatorMirror` / `operator`, a evidencia atual associa essa entidade ao Provedor/ISP do Link: `CMDBLinkMirror.isp_raw` referencia `source_config_item_id` do catalogo e o rotulo e `name`. A estrutura foi preservada sem migration ou rename. `legacy_project` permanece valor historico, sem equivalencia oficial de Projeto; nao existe campo/relacao confirmada para a Operadora contratada. O DTO `LinkSemantics` deixa ambos como nao classificados.

A busca da Base aplica normalizacao Unicode somente a texto apresentado; ConfigItemID, Number, Circuito e Designacao sao pesquisados mantendo seus caracteres.
