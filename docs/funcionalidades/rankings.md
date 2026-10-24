# Rankings operacionais · NOC Atacado

O módulo **Rankings** compara o risco operacional de Providers/ISPs do CMDB e tickets espelhados do OTRS. A identidade do produto continua **ARION ATACADO GEO**; NOC Atacado identifica a operação atendida. Todas as consultas usam mirrors locais em modo somente leitura.

## Universo, escopo e filtros

- Links são registros atuais `CMDBLinkMirror.is_present_in_source=True`. Provider é a operadora/ISP vinculada ao link no CMDB; Cliente e Projeto vêm de `contracting_client` e `business_project` canônicos.
- O Data Scope de Operadora/Projeto é aplicado por `LinkQueryService.base(user)` antes dos filtros, tickets relacionados, dimensões e scores. O drawer refaz a consulta sob o mesmo usuário e escopo.
- Tickets pertencem à fila `NOC - ATACADO`, estão presentes na fila e têm um estado operacional válido: `OPEN`, `PENDING`, `SCHEDULED`, `RESOLVED` ou `CLOSED`. `CANCELED` e `UNKNOWN` não entram nas métricas operacionais.
- Tickets válidos no período usam `source_created_at`, no fuso `America/Sao_Paulo`, com início inclusivo e limite superior exclusivo no início do dia seguinte. O KPI nacional distinto sem filtros segue o mesmo universo semântico do Cockpit.
- Filtros disponíveis: mês, janela mensal/móvel de três meses, período personalizado, Cliente, Projeto, Provider, UF, prioridade OTRS, motivo normalizado, estado operacional, apenas Aging >24h e apenas reincidentes.

Um ticket relacionado a vários ConfigItems do mesmo Provider conta uma vez para esse Provider, enquanto cada link distinto afetado conta uma vez. Se os links do ticket pertencem a Providers diferentes, o ticket conta uma vez em cada Provider; portanto, a soma dos tickets por Provider pode superar o KPI nacional de tickets distintos. Essa diferença decorre do agrupamento e é intencional.

## Métricas

- **Links CMDB:** links atuais no Provider dentro do Data Scope e dos filtros comerciais/geográficos.
- **Tickets:** tickets válidos distintos criados no intervalo selecionado e associados aos links do Provider.
- **Links afetados:** links distintos com pelo menos um ticket válido no intervalo; não depende de o ticket continuar aberto.
- **Reincidência:** um link tem reincidência quando possui pelo menos dois tickets válidos distintos criados no mesmo intervalo. `recurrent_rate = recurrent_links / links_affected`; sem links afetados, a taxa é zero.
- **Backlog atual:** tickets distintos hoje em `OPEN`, `PENDING` ou `SCHEDULED`.
- **ARION >24h:** soma de tickets atualmente abertos há mais de 24 horas desde `source_created_at` e tickets `RESOLVED`/`CLOSED` do período cuja duração `terminal_state_at - source_created_at` excede 24 horas. `resolved_at` não é usado como substituto universal do timestamp terminal.
- **Taxa >24h:** tickets ARION >24h divididos pelos tickets que possuem timestamps suficientes para avaliação. Tickets sem os timestamps necessários ficam fora do denominador; ausência de dado não é tratada como sucesso.
- **Criticidade:** participação de tickets com prioridade alta/crítica, baseada em mapeamento explícito dos nomes reais: `Alto`/`High` e `Crítico`/`Critico`/`Critical`, com normalização de acento e caixa. Não há detecção por substring.

O indicador de 24 horas é o **limite operacional provisório do ARION**. Não representa necessariamente o SLA contratual de cada Projeto/Cliente. Não há disponibilidade percentual, penalidade ou dado contratual estimado.

## Índice de Risco ARION V1

O índice fica entre 0 e 100; valores maiores indicam maior atenção operacional. Cada componente é convertido para percentil ordinal dentro do conjunto filtrado de Providers: ordenação por valor, percentil médio para empates e escala de 0 a 100 entre as posições mínima e máxima. Assim, um outlier não comprime os demais como ocorreria em min-max. Se todos os Providers empatam ou há somente um, o componente recebe zero.

O **Risco proporcional** pesa 70% do índice e combina:

| Componente proporcional | Peso |
|---|---:|
| Taxa de links afetados | 25% |
| Tickets por 100 links | 20% |
| Taxa de reincidência | 20% |
| Taxa ARION >24h | 20% |
| Backlog por 100 links | 10% |
| Criticidade Alto/Crítico | 5% |

O **Impacto absoluto** pesa 30% e combina tickets do período (40%), links afetados (30%), tickets ARION >24h (20%) e backlog atual (10%).

Os pesos e a exposição mínima são centralizados em `RANKING_WEIGHTS` e `SMALL_SAMPLE_LINK_THRESHOLD` no service de Rankings. Provider com menos de cinco links permanece no ranking e recebe a marca **Amostra pequena**, sem redução artificial de taxa ou score. Quando os scores proporcionais e de impacto divergem, ambos ficam disponíveis no detalhe.

Faixas de apresentação: 0–19,9 Muito bom; 20–39,9 Atenção baixa; 40–59,9 Atenção; 60–79,9 Alto risco; 80–100 Crítico. São categorias internas de priorização, não metas contratuais.

## Período móvel e tendência

O padrão é o mês selecionado até hoje quando for o mês corrente; meses anteriores usam o mês calendário completo. **3 meses** soma os dados brutos desde o primeiro dia de dois meses antes até o fim do mês selecionado (ou hoje, se corrente) e recalcula os componentes e o score sobre esse agregado. Scores mensais não são somados.

A tendência exibida em cada Provider compara o score recalculado do mês selecionado com o mês calendário anterior: diferença acima de 2 pontos indica piora, abaixo de -2 indica melhora; entre esses limites é estável. O drawer também mostra os scores dos três meses calendário mais recentes disponíveis no recorte.

## Ranking de links e detalhe

O ranking por circuito apresenta 20 links por padrão e permite abrir a lista completa. Projeto e Cliente usam as dimensões canônicas do CMDB. O detalhe do Provider reúne evolução do índice, principais Projetos, Clientes, UFs com bandeiras locais, motivos normalizados, links mais problemáticos, tickets ARION >24h e backlog atual. As ações abrem Base e Cockpit com os filtros de Provider/período correspondentes. Não são enviados dados fora do escopo autorizado.

## Consistência e limites

O KPI **Tickets válidos** nacional, sem filtros adicionais, corresponde ao Cockpit para a mesma janela de criação e estados operacionais; ele inclui tickets da fila que ainda não têm vínculo com um link atual. A soma por Provider pode ser maior por causa de tickets associados a mais de um ISP, ou menor quando tickets não têm Provider identificável. O Mapa agrega tickets por UF e não inclui tickets relacionados somente a links sem UF normalizável em seu total estadual; essa diferença de cobertura geográfica não altera as regras do Mapa.

Os rankings são derivados dos campos disponíveis nos mirrors. O módulo não infere contrato, disponibilidade, causa técnica ou responsabilidade do Provider. Pesos, faixas e limiar de amostra são uma primeira versão operacional e podem ser ajustados quando a governança de SLA por Projeto/Cliente for definida.


## Maior risco e melhor desempenho

A URL mantém `ranking_view=risk` (padrão) ou `ranking_view=best`. Maior risco usa a ordenação descendente da visão ativa; Melhor desempenho ordena o mesmo Índice ARION V1 em ordem crescente, sem inverter a escala. Empates de melhor desempenho priorizam maior exposição de links e depois o nome do Provedor / ISP. `BEST_RANKING_MIN_LINKS = 5` centraliza a elegibilidade do pódio de melhores. Providers com menos links continuam na tabela e podem aparecer no pódio de risco, com a marca Amostra pequena; não entram no pódio positivo. O total de links permanece exposto para contextualizar resultados sem tickets.

## Procedência observada no OTRS

Estudo read-only do OTRS localizou em `dynamic_field` o campo de Ticket `RvalidacaoProcedenteImprocedente`, label `Validação`, tipo `Dropdown`; os valores ficam em `dynamic_field_value`. No snapshot consultado em 24/10/2026, 1.848 de 11.973 tickets da fila tinham valor: 1.505 `Procedente` e 343 `Improcedente` (15,43% preenchido). O cruzamento com `CodigoFechamento` mostrou motivos iguais sob as duas classificações, portanto a categoria não prova culpa ou responsabilidade do Provider, Cliente ou área técnica.

O mirror guarda `responsibility_raw` e `responsibility_normalized`: valores reconhecidos, sem distinção de caixa/acentos, tornam-se `PROCEDENTE` ou `IMPROCEDENTE`; campo vazio ou outro valor vira `INDETERMINADO`. O resumo do Provider conta tickets distintos do período, e a taxa de procedência usa somente `PROCEDENTE + IMPROCEDENTE` como denominador. A marca informativa **Revisar responsabilidade** requer ao menos seis tickets conhecidos e 60% ou mais classificados como improcedentes; não afirma falso positivo. Esses dados não alteram o Índice ARION V1.

O detalhe inclui resumo, barra proporcional, motivos com contagens de procedentes/improcedentes, dimensões de Projeto/Cliente/UF, links com as duas classificações e tickets paginados em lotes de 10 ou 50. O modal mostra campos operacionais do mirror, sem artigos, notas internas, anexos, e-mail ou telefone; contatos reconhecíveis no título são removidos na resposta.

## Exportação e navegação para a Base

PDF e XLSX são gerados pela consulta atual, com filtros de período, visão e dimensões preservados. PDF contém metadados de geração, KPIs, pódio, até 20 Providers e totais de responsabilidade observados; XLSX contém as abas Resumo, Ranking, Providers, Links e Tickets, sem a paginação da tela. O serviço aplica `LinkQueryService.base(user)` antes dos dados, de modo que detalhe e exportação respeitam o Data Scope.

O link individual do Ranking abre a Base por `config_item_id` exato e não transmite Cliente/Projeto/UF/Provider herdados. Na Base, a chave técnica é resolvida dentro do queryset já limitado por Data Scope; dimensões antigas ou contraditórias são ignoradas para esse destino, mas um CI fora do escopo continua sem resultado. O botão de lista do Provider mantém o filtro de Provider para mostrar vários links acessíveis.

## Governança futura

A próxima versão pode avaliar um score ajustado por responsabilidade após aprovação semântica, além de SLA por Projeto, disponibilidade observada, janela operacional e penalização contratual. Esses conceitos não são calculados nesta versão e não alteram a V1.
