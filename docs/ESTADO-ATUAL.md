# Estado atual do ARION ATACADO GEO

Atualizado em 24/10/2026.

## Identidade e Dashboard

Nome oficial/visual do produto: **ARION ATACADO GEO**. **NOC ATACADO** identifica a operação atendida.

O Dashboard mantém os KPIs, a situação atual dos chamados e o gráfico do período. A linha inferior apresenta Top 10 Estados e Top 10 Provedores calculados sobre o snapshot CMDB atual e Data Scope. A classificação legada VIVO / CLARO / ALGAR / OUTROS saiu da apresentação; o campo e sua migration permanecem no banco.

O Cockpit analisa Tickets atuais da fila `NOC - ATACADO`. `CodigoFechamento` é sincronizado como `closing_code_raw`; aliases de Pendência Financeira são normalizados explicitamente, sem juntar motivos distintos de cancelamento. `ticketResolvido` é espelhado em `resolved_at`, mas o período terminal usa `terminal_state_at`, derivado do último `StateUpdate` que corresponde ao estado terminal atual. Cancelamentos têm `canceled_at` próprio e ficam fora das métricas de sucesso. Tickets criados continuam usando `source_created_at`. Snapshots de atendimento, pendência, agendados e backlog seguem Data Scope e não são reduzidos por filtros históricos. A composição completa é paginada e exportações compartilham a mesma análise.

`SCHEDULED` (Agendado) é distinto de `PENDING`; ambos, junto de `OPEN`, compõem o backlog pelo snapshot atual da fila.

A Home está organizada como central de acesso operacional, administrativo e de conta. Os cards respeitam as permissões dos módulos; Documentação usa `configuracoes.manage_groups`, e ARI usa `configuracoes.view_ari`. Os contadores usam o queryset CMDB escopado e a mesma lista de UFs válidas do Dashboard.
## Dados operacionais

Base, Dashboard, Cockpit, Mapa e Rankings consultam os mirrors CMDB/OTRS no banco Arion. Requests nao fazem chamadas externas. CMDB fornece Links e Operadoras; OTRS fornece tickets atuais da fila `NOC - ATACADO` e relacoes validas Ticket-ConfigItem. O snapshot local anterior permanece disponivel se a origem falhar.

XLSX esta aposentado como fonte operacional. Modelos, migrations e servicos antigos permanecem para rollback; interface normal de importacao esta desativada. `project_legacy` representa valor congelado transitorio, marcado `LEGACY_XLSX`, sem status de dado oficial.

## Banco primario

O Arion suporta SQLite e MySQL; SQLite e usado no desenvolvimento/portatil e MySQL e o destino de producao. Neste checkout, o banco ativo no processo e no bootstrap continua SQLite. O candidato `127.0.0.1:3306/arion_geo` passou no dry-run e esta com schema preparado (39 migrations); copia de dados, validacao e ativacao ainda estao pendentes. MySQL Server 8.0.46/schema `arion_geo` foi validado anteriormente e nao esta ativo nesta execucao. A Central agora separa banco ativo de candidato e so muda o proximo boot apos testar, preparar migrations, copiar dados, validar e ativar. O rollback e manual e nao ha fallback silencioso. O copy cria backup SQLite consistente e preserva usuarios, grupos, permissoes, escopos, consultas salvas, preferencias, auditoria e configuracoes; mirrors sao limpos no candidato e reconstruidos pelas fontes oficiais. A senha MySQL local e protegida com DPAPI vinculada ao usuario Windows. A conexao externa OTRS permanece independente e read-only.

## Snapshot reconstruido no MySQL

A sincronizacao inicial concluiu: 3.437 Links, 1.330 Operadoras/Provedores, 11.972 tickets da fila `NOC - ATACADO` e 7.505 relacoes Ticket-ConfigItem. Foram preenchidos `closing_code_raw` em 10.310 tickets, `resolved_at` em 11.913, `terminal_state_at` em 11.954 e `canceled_at` em 986. No snapshot observado, backlog OPEN + PENDING + SCHEDULED = 6 + 5 + 7 = 18; esses valores variam conforme a fonte.

## Atualizacao

Worker separado: `.venv\Scripts\python.exe arion_geo\gerenciar.py integration_worker`.

- OTRS fast: 2 min; full reconcile: 30 min.
- CMDB full: 10 min.
- Lock de fonte persistente, heartbeat e lease expiravel.
- Cursor OTRS por `change_time` com safety window de 2 min; delta atualiza somente tickets afetados e suas relacoes em lote.
- Freshness local aparece na Central de Integracoes.
- No MySQL local, as integracoes CMDB e OTRS foram reconfiguradas pela Central, testadas e habilitadas. A sincronizacao inicial CMDB/FULL OTRS e um ciclo OTRS FAST do worker foram concluidos; lease, IntegrationRun e cursor FAST estao persistidos no MySQL.

A aplicacao web funciona sem worker usando o ultimo snapshot, que passa a stale.

## Analytics e acesso

KPIs nao suportados por fonte real (como SLA cumprido) nao sao simulados nos modulos operacionais. Periodo de tickets usa data de criacao; backlog e status atual. Tickets sao distintos nos KPIs gerais e podem contar por cada Link relacionado. Data Scope CUSTOM restringe Link por Operadora E Projeto legado; tickets sem relacao permitida nao sao mostrados.

ARI segue Preview demonstrativa separada. Nao ha modulo Chamados nem acoes de escrita no OTRS.
