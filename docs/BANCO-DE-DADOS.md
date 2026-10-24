# Banco de dados e espelhos operacionais

As paginas operacionais usam os mirrors do app `integracoes`; as tabelas antigas de Base XLSX permanecem apenas para rollback e historico.

## Cadeia de relacionamento

`OTRSTicket` -> `OTRSTicketConfigItem.config_item_id` (OTRS `link_relation.source_key`) -> `CMDBLinkMirror.source_config_item_id` (CMDB `ConfigItemID`) -> `CMDBLinkMirror.operator` -> `CMDBOperatorMirror`.

`source_number` corresponde ao identificador de negocio `Number`/antigo `ConfigItem#`, mas nao substitui `ConfigItemID` como chave da relacao Ticket-CI. Relacoes sem mirror local preservam `cmdb_link=NULL`; multiplos CIs por ticket sao suportados.

## Modelos

- `CMDBOperatorMirror`: campos seguros de operador e presenca na origem.
- `CMDBLinkMirror`: atributos CMDB, FK opcional de operadora, `legacy_project` transitorio e `is_present_in_source`.
- `OTRSTicket`: fila, estado de negocio, prioridade, servico, SLA por nome, datas de criacao/alteracao, `closing_code_raw`, `resolved_at`, `terminal_state_at`, `canceled_at`, `responsibility_raw`, `responsibility_normalized` e `is_present_in_queue`.
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

## Datas e motivo de fechamento no mirror OTRS

`integracoes.OTRSTicket` espelha `closing_code_raw` (Dynamic Field `CodigoFechamento`), `resolved_at` (Dynamic Field DateTime `ticketResolvido`), `terminal_state_at` (último `StateUpdate` correspondente ao estado terminal atual), `canceled_at` (o mesmo evento quando o estado atual é cancelado), `responsibility_raw` e `responsibility_normalized` (Dynamic Field Ticket `RvalidacaoProcedenteImprocedente`). O Arion não grava no banco OTRS. Esses campos são preenchidos no FULL e atualizados para tickets alterados no FAST. A classificação de responsabilidade preserva o texto da origem e mapeia apenas Procedente/Improcedente conhecidos; não comprova atribuição causal nem altera o Índice ARION V1.

## Banco primario do Arion

O banco primario suportado e SQLite ou MySQL. `DATABASE_URL` prevalece sobre a configuracao local `var/database-config.json`, que fica fora do banco; sem ambos, a aplicacao usa `arion_geo/db.sqlite3`. A senha MySQL da configuracao local e protegida por DPAPI do usuario Windows atual. A Central mantem banco ativo e MySQL candidato separados. Salvar candidato nao altera o boot; ativacao exige teste, schema, copia e validacao e vale apos reiniciar web e worker. A conexao externa OTRS segue separada, read-only, e nao e substituida por esta configuracao.


## Validacao do ambiente MySQL local

Ambiente local validado com MySQL Server 8.0.46 e schema `arion_geo`; a Central executou o teste real de conexao. As migrations foram aplicadas e os mirrors iniciais reconstruidos: 3.437 Links, 1.330 Operadoras/Provedores, 11.972 tickets e 7.505 relacoes Ticket-ConfigItem. O estado do backlog no momento da sincronizacao foi OPEN=6, PENDING=5 e SCHEDULED=7 (18 no total), sujeito a mudanca na origem. O `db.sqlite3` anterior foi mantido para rollback.


## Fluxo seguro SQLite -> MySQL

`var/database-config.json` mantem `active`, `candidate`, `rollback` e o estado por fingerprint do candidato. Arquivos antigos no formato plano continuam sendo lidos como banco ativo, sem reinterpretacao como candidato. A senha do candidato e protegida com DPAPI do usuario Windows atual; credenciais de outro usuario precisam ser informadas novamente. Falha de autenticacao 1045 e exibida como acesso negado e bloqueia as etapas seguintes. Nao ha fallback silencioso: se o MySQL ativo falhar no boot, use rollback explicito.

Fluxo: salvar candidato -> testar conexao (SELECT DATABASE(), VERSION(), NOW()) -> preparar schema com migrations Django -> copiar dados locais -> validar -> ativar -> reiniciar servidor web e integration_worker. O comando de cada etapa e:

```powershell
.venv\Scripts\python.exe arion_geo\gerenciar.py migrar_banco_arion --target=mysql --dry-run
.venv\Scripts\python.exe arion_geo\gerenciar.py migrar_banco_arion --target=mysql --prepare
.venv\Scripts\python.exe arion_geo\gerenciar.py migrar_banco_arion --target=mysql --copy-local-data
.venv\Scripts\python.exe arion_geo\gerenciar.py migrar_banco_arion --target=mysql --validate
.venv\Scripts\python.exe arion_geo\gerenciar.py migrar_banco_arion --target=mysql --activate
```

As opcoes de fase sao mutuamente exclusivas; `--activate` nunca migra ou valida automaticamente. Para reverter no proximo boot: `.venv\Scripts\python.exe arion_geo\gerenciar.py migrar_banco_arion --target=mysql --rollback`. Se o Django nao iniciar por falha DPAPI/credencial ativa, use `.venv\Scripts\python.exe arion_geo\rollback_banco_arion.py`, que nao carrega settings Django. Se `DATABASE_URL` estiver definida, remova-a do ambiente de web/worker para que a configuracao bootstrap local tenha efeito. O rollback apenas troca a configuracao ativa e nao apaga o MySQL.

Antes da copia, a rotina cria snapshot consistente do SQLite pela API `sqlite3.Connection.backup()` em `var/backups/db-before-mysql-*.sqlite3` (diretorio ignorado pelo Git). Models preservados: usuario Django (hash incluido), grupos, permissoes e relacoes usuario-grupo/permissoes, Operadora/Projeto usados por escopos, GroupDataScope e LegacyUserDataScope e suas relacoes, UserPreference, SavedAnalyticsView, Integration (credenciais reabertas e protegidas novamente por DPAPI) e AuditEvent. ContentType e Permission sao gerados pelas migrations Django; permissoes e relacoes sao remapeadas por app/model/codename. A rotina e reexecutavel para as chaves naturais mapeadas e evita duplicar eventos de auditoria.

Nao sao copiados CMDBLinkMirror, CMDBOperatorMirror, OTRSTicket ou OTRSTicketConfigItem; apos ativar, reconstrua os mirrors das fontes oficiais com CMDB FULL e OTRS FULL. `IntegrationLease`, `IntegrationRun` e `IntegrationSyncState` nao sao copiados; qualquer estado existente no candidato e limpo durante a copia. Leases/cursors antigos podem estar vencidos ou apontar para outro snapshot; as sincronizacoes devem iniciar limpas no destino. Configuracoes/segredos de integracao sao preservados e os estados de teste/saude locais sao zerados. OTRS continua externo e somente leitura.

A validacao verifica migrations, tabelas/modelos locais, contagens, permissoes e relacoes, hash/flags dos usuarios e capacidade de reabrir credenciais DPAPI no usuario Windows atual. A ativacao exige candidato ainda testado, preparado, copiado e validado para o fingerprint atual. Em falha depois da ativacao, rollback manual restaura o SQLite configurado previamente ou o `arion_geo/db.sqlite3` legado, se existir; reinicie web e worker.
