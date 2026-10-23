# Estado atual do ARION ATACADO GEO

Atualizado em 23/10/2026.

## Dados operacionais

Base, Dashboard, Cockpit, Mapa e Rankings consultam os mirrors CMDB/OTRS no banco Arion. Requests nao fazem chamadas externas. CMDB fornece Links e Operadoras; OTRS fornece tickets atuais da fila `NOC - ATACADO` e relacoes validas Ticket-ConfigItem. O snapshot local anterior permanece disponivel se a origem falhar.

XLSX esta aposentado como fonte operacional. Modelos, migrations e servicos antigos permanecem para rollback; interface normal de importacao esta desativada. `project_legacy` representa valor congelado transitorio, marcado `LEGACY_XLSX`, sem status de dado oficial.

## Atualizacao

Worker separado: `.venv\Scripts\python.exe arion_geo\gerenciar.py integration_worker`.

- OTRS fast: 1 min; full reconcile: 30 min.
- CMDB full: 10 min.
- Lock de fonte persistente, heartbeat e lease expiravel.
- Cursor OTRS por `change_time` com safety window de 2 min.
- Freshness local aparece na Central de Integracoes.

A aplicacao web funciona sem worker usando o ultimo snapshot, que passa a stale.

## Analytics e acesso

KPIs nao suportados por fonte real (como SLA cumprido) nao sao simulados nos modulos operacionais. Periodo de tickets usa data de criacao; backlog e status atual. Tickets sao distintos nos KPIs gerais e podem contar por cada Link relacionado. Data Scope CUSTOM restringe Link por Operadora E Projeto legado; tickets sem relacao permitida nao sao mostrados.

ARI segue Preview demonstrativa separada. Nao ha modulo Chamados nem acoes de escrita no OTRS.
