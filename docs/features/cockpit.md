# Cockpit Operacional

O Cockpit está disponível em `/cockpit/`, separado do Dashboard executivo.
Ele concentra investigação por métrica, período, comparação e dimensão, com
filtros adicionais, consultas rápidas, detalhamento e exportação.

## Consulta e fontes

`AnalyticsQueryService` valida métricas, agrupamentos, períodos e filtros. A
`CMDBAnalyticsSource` consulta CMDB real e aplica `DataScopeService` à QuerySet
antes de agregar dados. `DemoOperationalAnalyticsSource` deriva indicadores
operacionais determinísticos somente das linhas CMDB autorizadas. Tickets,
status, SLA, backlog, recorrência, motivos e tempo continuam identificados como
demonstrativos; não existe conexão OTRS.

Uma resposta normalizada fornece KPIs adequados à métrica, série temporal,
distribuição e tabela detalhada. Dimensões incompatíveis com Links são recusadas
pelo serviço e desabilitadas na interface.

## Estado da consulta

O estado da consulta fica no JavaScript do Cockpit e é serializado nos query
params da rota `/cockpit/`. Atualizações, voltar/avançar e recarregamento
reconstroem os mesmos filtros. Consultas rápidas são presets desse estado; uma
alteração manual identifica o preset como modificado. Limpar filtros restaura a
consulta padrão, limpa os parâmetros e inicia uma nova consulta sem recarregar a
página. Requisições anteriores são canceladas e somente a consulta mais recente
pode renderizar resultado.

## Consultas salvas e exportação

`SavedAnalyticsView` guarda a configuração por usuário, sem persistir resultados.
O Cockpit permite salvar, abrir, renomear e excluir consultas. Ao reabrir, executa
novamente a consulta sob as permissões e o Data Scope atuais.

`POST /api/analytics/query/` retorna a consulta normalizada.
`POST /api/analytics/saved-views/` lista e altera consultas privadas do usuário.
`POST /api/analytics/export/` exporta o mesmo estado e aplica o mesmo Data Scope:
CSV em UTF-8 com BOM, XLSX com abas Resumo e Dados e PDF executivo em A4, com
KPIs, gráficos vetoriais e tabela detalhada paginada. O XLSX usa `openpyxl` e o
PDF usa `reportlab`; ambos são dependências Python declaradas pelo projeto. Não
há dependência frontend adicional.

O Dashboard continua consumindo `AnalyticsQueryService.dashboard_snapshot()`
para manter a série demonstrativa nacional consistente com o Cockpit.
