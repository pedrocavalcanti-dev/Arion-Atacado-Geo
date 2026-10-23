# Arquitetura

## Fluxo de dados

Fontes externas -> sincronizadores dedicados -> mirrors no banco Arion -> query/services compartilhados -> views, APIs e exportacoes. Requests de Base, Dashboard, Cockpit, Mapa e Rankings nao consultam CMDB nem OTRS.

CMDB ServiceUp alimenta `CMDBOperatorMirror` e `CMDBLinkMirror`. OTRS MySQL read-only alimenta `OTRSTicket`, mapeamentos de estado e relacoes Ticket-ConfigItem. `LinkQueryService`, `TicketQueryService` e `PeriodService` centralizam universo local, Data Scope e datas; modulos analiticos reutilizam esses servicos.

## Scheduler

`integration_worker` e uma management command para processo separado do servidor HTTP. Nao e iniciado por view, middleware ou `AppConfig.ready()`. Cadencias: OTRS fast 1 min, OTRS full 30 min, CMDB full 10 min. Lease persistente por fonte impede concorrencia entre worker e comando manual; heartbeat de 20 s renova expiracao de 180 s. SQLite em desenvolvimento e MariaDB em producao usam a mesma tabela local.

OTRS incremental consulta `ticket.change_time` com janela de seguranca de 2 minutos, inclui tickets conhecidos que sairam da fila e recarrega relacoes em lotes. Primeira execucao exige full. Cursor so avanca apos persistencia local confirmada. Falha preserva snapshot e cursor.

## Data Scope e semantica

Query layer aplica Data Scope as linhas Link antes de filtrar/agregar. CUSTOM usa intersecao Operadora + Projeto. Projeto usa `legacy_project` congelado e nao oficial; falta de Projeto nao amplia acesso. Tickets sem Link permitido sao invisiveis para CUSTOM. Metricas gerais usam IDs distintos; contagem por Link pode incluir o mesmo ticket em mais de um Link.

Datas de volume filtram `source_created_at`; backlog e estados atuais sao fotografia corrente, nao historico reconstruido. Nao ha calculo de SLA cumprido sem regra validada.

## Legacy e limites

O importador/modelos XLSX permanecem para rollback, mas nenhuma pagina operacional le o legado e a rota de upload esta desativada. ARI Preview permanece demonstrativa e separada. Modulo Chamados e escrita de ticket OTRS nao fazem parte desta fase.
## Camada semantica operacional

`LinkSemantics` centraliza os rotulos seguros: Provedor vem do nome da entidade CMDB resolvida; Projeto oficial e Operadora contratada permanecem sem classificacao ate haver fonte confirmada. IDs e ISP bruto continuam apenas como dados tecnicos. `TicketQueryService.noc_tickets()` fixa o universo da fila pelo nome exato `NOC - ATACADO`; periodos usam a data de criacao e backlog usa o snapshot atual OPEN + PENDING independentemente do periodo.
