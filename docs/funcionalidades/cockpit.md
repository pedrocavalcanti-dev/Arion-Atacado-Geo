# Cockpit

O Cockpit consulta somente o espelho local dos Tickets atuais da fila exata `NOC - ATACADO`. Data Scope entra no queryset antes das opções, filtros, métricas, grupos e exportações. O OTRS é fonte oficial e o Arion permanece uma camada de consulta; nenhuma requisição do Cockpit consulta MySQL do OTRS.

## Fechamento e motivo

`CodigoFechamento` (Dynamic Field Ticket ID 101) e sincronizado para `OTRSTicket.closing_code_raw`, sem sobrescrever o raw. `ClosingReasonCanonicalizer` centraliza a regra `raw -> canonical key -> display label`, usada em filtro, agrupamentos, KPIs, calendario, evidencias e exportacoes. `FalhaMassiva`, `Falha Massiva` e `Defeito Massivo` usam a chave `falha_massiva` e uma unica serie. O dropdown usa chaves estaveis, por exemplo `termination_reason=falha_massiva`; URLs antigas com raw conhecido tambem sao resolvidas.

O dropdown exibe uma opcao por categoria canonica, ordenada pelo label humano e com a chave canonica como valor. Alem dos aliases anteriores, `Equipamento travado/reinicilizado` + `EquipamentoTravado`, `Rompimento/manut Fibra` + `RompimentoFibra`, `Cancelado` + `ChamadoCancelado`, e `Conexao Incorreta - Cabeamento/porta` + `ConexaoIncorreta` sao consolidados. `CancelamentoServico` permanece separado. URLs e consultas salvas com raws antigos sao resolvidas para a chave canonica ao carregar. O detalhe do ticket e a exportacao incluem o label canonico; CSV/XLSX/PDF tambem preservam o valor raw em coluna propria. Detalhe de fechamento em texto livre nao e importado. Inventario historico de aliases: `docs/estudos/OTRS-MOTIVOS-FECHAMENTO.md`; regra normativa atual: [OTRS](../OTRS.md).

`ticketResolvido` é sincronizado para `resolved_at` e passou a ser a data principal de término operacional. Nas análises de `RESOLVED` e `CLOSED`, usa-se `resolved_at`; se estiver ausente, usa-se `terminal_state_at`, derivado do último `StateUpdate` compatível com o estado terminal atual. Se ambos faltarem, o registro não recebe data inventada nem entra em métrica temporal/duração final. `business_status=CLOSED` continua representando o estado oficial atual do OTRS. A comparação histórica contra `ticket_history` / `StateUpdate` encontrou correspondência de até um minuto em 18/18 tickets `resolvido`; entre tickets `closed successful` com ambos os valores, 10.727/10.944 ficaram até um dia e 217 divergiram mais de um dia. Essa divergência continua disponível para diagnóstico; não muda a precedência operacional. `canceled_at` permanece separado para tickets atualmente cancelados. Não há leitura de histórico durante as requisições.

## Métricas, estados e datas

O universo de métricas gerais contém `OPEN`, `PENDING`, `SCHEDULED`, `RESOLVED` e `CLOSED`. `CANCELED` aparece somente na métrica específica Cancelados; `UNKNOWN` fica fora das métricas gerais. `Tickets criados` usa `source_created_at` e conta tickets distintos válidos conforme todos os filtros ativos. Métricas de situação operacional atual também se baseiam na criação e no estado atual. `Backlog atual` é snapshot: tickets presentes na fila em `OPEN`, `PENDING` ou `SCHEDULED`.

`Resolvidos`, `Tickets em CLOSED, resolvidos no período` e `Resolvidos + CLOSED` filtram, agrupam e comparam pela data de resolução operacional (`resolved_at`, com fallback `terminal_state_at`) e preservam o estado OTRS correspondente. `Cancelados` usa `canceled_at`. `Tickets criados` e métricas por criação continuam usando `source_created_at`. O filtro Motivo usa o valor categórico normalizado `CodigoFechamento`. A consulta de Pendência Financeira preserva a métrica e o intervalo escolhidos. A descrição dinâmica da consulta é compartilhada pela tela e pelo PDF.

Data Scope é aplicado antes do universo operacional, filtros, KPIs, agrupamentos e exportações. Resumo, visão geral, calendário, dimensões e tickets usam o mesmo queryset de análise. A visão geral usa granularidade diária até 31 dias, semanal de 32 a 90 dias e mensal acima de 90 dias. Abaixo dela, o calendário mostra os dias do mês selecionado; o padrão é o último mês com dados e o seletor contém somente meses que intersectam o período. Dias fora de um intervalo parcial ficam desativados. A visão geral mensal permite selecionar o mês do calendário. Clicar em um dia abre ações para filtrar temporariamente a lista de tickets ou aplicar aquele dia como novo período.

Gráficos de dimensão são omitidos quando a dimensão já está filtrada ou não há variação. O ranking principal ocupa a largura disponível, limita-se aos dez primeiros e a distribuição completa permanece recolhida. Até dois gráficos complementares usam outras dimensões relevantes. A comparação automática usa o mês anterior completo para um mês-calendário e, nos demais períodos, uma janela anterior de igual duração. Backlog não tem comparação histórica.

No Cockpit, o resumo do recorte fica no cabeçalho e os KPIs vêm logo após os filtros. Visão geral temporal e calendário permanecem sempre visíveis. As dimensões, a distribuição completa e a lista de tickets podem ser recolhidas separadamente; os três controles também têm uma ação global. A preferência de recolhimento dura apenas a sessão do navegador e não dispara consultas. Ao escolher **Ver tickets deste dia**, a lista se abre e a tela navega até ela; **Aplicar dia como período** mantém o fluxo de consulta principal.

O ranking mostra somente provedores resolvidos; tickets sem provedor permanecem no total e aparecem na qualidade dos vínculos. A participação do ranking usa tickets com provedor identificado como denominador. Composição e ranking são separados da seção **Tickets do resultado**, que lista os registros com paginação e busca dentro do universo filtrado. O drawer apresenta datas, estado, motivo, prioridade, SLA, campos CMDB seguros e evidências dos filtros e Data Scope. Relações CMDB são pré-carregadas para evitar N+1.

## Resultados e exportação

A lista de tickets mostra 25 por página, com opções 50 e 100. A busca considera número do ticket, ConfigItem, Number, designação, circuito e provedor e não altera os totais ou gráficos da consulta.

PDF, CSV e XLSX chamam o mesmo `AnalyticsQueryService` e exportam todos os tickets do resultado, respeitando Data Scope. O PDF inclui título dinâmico, usuário e horário de geração, resumo executivo, visão geral, calendário do mês selecionado, ranking em tabela, gráficos complementares e anexo de tickets. Não repete a distribuição completa do ranking no corpo. Usa fonte Unicode Vera. CSV é UTF-8 com BOM e contém os tickets; XLSX tem abas `Resumo`, `Distribuição` e `Tickets`. Nenhum formato inclui campos pessoais do cliente ou conteúdo de artigos.

Na primeira abertura, a tela mostra placeholders de filtros, KPIs, gráficos e tabelas. Atualizações posteriores preservam os filtros e mostram um estado discreto de carregamento dos resultados. O Cockpit não inicializa consultas ou sincronizações durante carregamento de página; apenas lê o espelho local.


## Implementação e operação

Views e serviço do app `painel` alimentam `/cockpit/`; a API compartilhada de consulta fica em `/api/analytics/query/`, exportação em `/api/analytics/export/` e views salvas em `/api/analytics/saved-views/`. A série temporal respeita a timezone do projeto (`America/Sao_Paulo`). O intervalo é `[start, end_exclusive)`; a granularidade muda conforme a duração selecionada.

A mesma query normalizada e limitada por Data Scope alimenta KPIs, séries, calendário, evidências e exportação. Status atual e volume por data de criação são conceitos distintos. Gráficos de tendências não equivalem a histórico reconstruído de backlog. Saved Views pertencem ao usuário atual e não ampliam scope nem permissions.

Código principal: `aplicativos/painel/services/analytics.py`, views do app `painel`, templates `templates/painel/` e fonte JS `frontend_src/js/painel/cockpit.js`. CSV/XLSX/PDF passam pela validação e queryset já autorizado.

## Contagem histórica e reincidência

`Tickets` conta chamados distintos do recorte histórico selecionado; `Links afetados` conta Links locais distintos associados a esses Tickets. A relação pode ser N:N: um Ticket pode afetar vários Links, e vários Tickets no mesmo Link não multiplicam o Link. Data Scope e filtros são aplicados antes das contagens. Para agrupamentos por Provedor, um Ticket pode participar de cada Provedor ao qual está relacionado, embora permaneça único no total nacional.

`Links reincidentes` é uma métrica histórica independente: conta Links distintos que atingem a regra de recorrência do período, baseada em pelo menos dois Tickets distintos. Não deve ser interpretada como Links afetados agora. `Backlog atual` é o snapshot dos tickets atuais `OPEN`, `PENDING` e `SCHEDULED` e não reconstrói estados passados.
