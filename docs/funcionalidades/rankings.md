# Rankings operacionais · NOC Atacado

O módulo **Rankings** compara a pressão operacional dos provedores/ISPs do CMDB com chamados espelhados do OTRS. A identidade do produto permanece **ARION ATACADO GEO**; NOC Atacado identifica a operação atendida. As consultas usam somente os mirrors locais e não escrevem na origem.

## Universo, escopo e filtros

- Links são registros atuais `CMDBLinkMirror.is_present_in_source=True`. Provedor é a operadora/ISP vinculada ao link no CMDB; Cliente e Projeto usam `contracting_client` e `business_project` canônicos.
- O Data Scope de Operadora/Projeto é aplicado por `LinkQueryService.base(user)` antes de filtros, relações, dimensões e cálculos. O drawer refaz a consulta sob o mesmo usuário e escopo.
- Chamados pertencem à fila `NOC - ATACADO`, estão presentes na fila e têm status operacional válido: `OPEN`, `PENDING`, `SCHEDULED`, `RESOLVED` ou `CLOSED`. `CANCELED` e `UNKNOWN` não entram nas métricas.
- Chamados do período usam `source_created_at`, no fuso `America/Sao_Paulo`, com início inclusivo e limite superior exclusivo no início do dia seguinte. O KPI nacional distinto segue o mesmo universo semântico do Cockpit.
- Filtros: mês, visão mensal ou consolidado de três meses, período personalizado, Cliente, Projeto, Provedor, UF, prioridade OTRS, motivo normalizado, status, apenas Aging >24h e apenas reincidentes.
- Filtro e Top Motivos usam `ClosingReasonCanonicalizer`, compartilhado com Cockpit e Mapa. Valores raw sem equivalência confirmada permanecem separados.

Um chamado relacionado a vários ConfigItems do mesmo provedor conta uma vez para esse provedor; cada link distinto afetado conta uma vez. Se os links pertencem a provedores diferentes, o chamado conta uma vez em cada provedor. Por isso, a soma dos chamados por provedor pode superar o KPI nacional distinto.

## Métricas operacionais

- **Links CMDB:** links atuais do provedor dentro do Data Scope e dos filtros comerciais/geográficos.
- **Chamados:** chamados distintos válidos criados no período e relacionados aos links do provedor.
- **Chamados por link:** chamados válidos divididos pelos links CMDB atuais. A tela não usa a antiga taxa por 100 links.
- **Links afetados:** links distintos com pelo menos um chamado válido no período.
- **Reincidência:** um link reincide quando possui pelo menos dois chamados válidos distintos no período. A taxa é `links reincidentes / links afetados`; sem links afetados, é zero.
- **Backlog atual:** chamados distintos em `OPEN`, `PENDING` ou `SCHEDULED`.
- **ARION >24h:** chamados abertos há mais de 24 horas desde `source_created_at` e chamados `RESOLVED`/`CLOSED` do período cuja duração `terminal_state_at - source_created_at` supera 24 horas. `resolved_at` não substitui o timestamp terminal.
- **Taxa de aging:** chamados acima de 24h divididos pelos chamados avaliáveis com timestamps suficientes. Registros sem timestamps necessários ficam fora do denominador.

O limite de 24 horas é operacional do ARION e não representa necessariamente o SLA contratual. O módulo não estima disponibilidade, causa técnica, penalidade nem responsabilidade do provedor.

## Índice ARION V2 · atual

O índice varia de **0 a 100**. Zero representa ausência de pressão observada no período. Os cinco componentes arredondados a uma casa decimal somam o total:

| Componente | Peso | Cálculo |
|---|---:|---|
| Impacto no NOC | 30 pontos | 60% volume de chamados e 40% links afetados; cada volume é dividido pelo P95 do conjunto filtrado e limitado a 100% antes da ponderação. |
| Base afetada | 20 pontos | `links afetados / links CMDB`, limitado a 100%. |
| Reincidência | 20 pontos | `links reincidentes / links afetados`, limitado a 100%. |
| Aging ARION >24h | 20 pontos | `chamados >24h / chamados avaliáveis`. |
| Backlog atual | 10 pontos | `backlog / max(chamados válidos, 1)`, limitado a 100%. |

O P95 usa a regra de posto mais próximo sobre os provedores do recorte já filtrado; distribuição vazia ou P95 zero rende zero pontos naquele subcomponente. O score não tem piso estatístico. O P95 é metodologia interna e não aparece por linha na interface. Responsabilidade do fechamento é apenas informativa e não altera o V2.

Faixas: `0` Sem ocorrências; `0,1–19,9` Muito baixo; `20–39,9` Baixo; `40–59,9` Moderado; `60–79,9` Alto; `80–100` Crítico. Provedores sem chamados e sem backlog têm score zero e ficam fora das visões de risco e melhor desempenho.

Provedores com menos de cinco links continuam visíveis e recebem **Amostra pequena**. Eles permanecem elegíveis ao ranking de risco. Para o pódio de melhor desempenho exige-se chamado válido e pelo menos cinco links **ou** três chamados; provedores menores com eventos continuam na tabela.

## Visões e desempates

- **Maior risco:** inclui `chamados >= 1 OU backlog > 0`. A ordenação padrão é Índice ARION decrescente; empates usam Impacto no NOC, chamados e links afetados em ordem decrescente, depois nome.
- **Melhor desempenho:** inclui somente provedores com ao menos um chamado válido. Ordena o índice crescente; empates priorizam maior exposição, primeiro links CMDB e depois chamados avaliados. Zero eventos não são tratados como desempenho de atendimento.
- **Sem ocorrências:** inclui `chamados = 0 E backlog = 0`; exibe até 10 provedores por maior exposição de links e apresenta links, clientes, projetos e UFs.

Os atalhos de ordenação incluem Índice ARION, impacto no NOC, chamados, percentual da base afetada, reincidentes, chamados acima de 24h, backlog e links CMDB. A tendência conserva a diferença contra o mês anterior: `↓ Melhorou` em verde, `↑ Piorou` em coral e `→ Estável` em neutro; a faixa estável é de ±2 pontos.

## Período, consolidação e tendência

A visão mensal usa o mês selecionado (até hoje quando for o mês corrente). **Consolidado 3 meses** agrega os dados brutos desde o primeiro dia de dois meses antes até o fim do mês selecionado, ou hoje se for o mês corrente, e então recalcula o V2 uma vez. Não soma scores mensais. O gráfico histórico recalcula o V2 separadamente para cada mês.

A tendência compara o score recalculado do mês selecionado com o mês calendário anterior: diferença acima de 2 pontos indica piora, abaixo de -2 indica melhora; entre esses limites é estável. A análise não altera a fonte nem simula meta ou SLA.

## Consistência de cobertura

O KPI **Chamados válidos** nacional, sem filtros adicionais, corresponde ao Cockpit para a mesma janela de criação e estados operacionais; ele inclui chamados da fila sem vínculo com um link atual. A soma por provedor pode ser maior por causa de chamados associados a mais de um ISP, ou menor quando não há provedor identificável. O Mapa agrega por UF e não inclui chamados relacionados somente a links sem UF normalizável no total estadual; a diferença de cobertura geográfica não muda as regras do Mapa.

## Detalhe e links

O ranking de circuitos apresenta 20 links por padrão e permite abrir a lista completa. O drawer mostra a soma dos cinco componentes, a evolução mensal, principais projetos/clientes/UFs/motivos, links problemáticos e chamados paginados. Clientes, Projetos e Motivos têm contagens e atributos complementares separados visualmente. As ações abrem Base e Cockpit preservando os filtros apropriados e o Data Scope.

Procedentes, Improcedentes e Indeterminados vêm do campo de validação do OTRS. O estudo da origem localizou `RvalidacaoProcedenteImprocedente` (`Validação`, tipo `Dropdown`) em `dynamic_field`; os valores ficam em `dynamic_field_value`. No snapshot consultado em 24/10/2026, 1.848 de 11.973 chamados tinham valor: 1.505 `Procedente` e 343 `Improcedente` (15,43% preenchido). O cruzamento com `CodigoFechamento` encontrou motivos iguais sob as duas classificações; a categoria não prova culpa do provedor, cliente ou área técnica.

O mirror guarda `responsibility_raw` e `responsibility_normalized`: valores reconhecidos, sem distinção de caixa/acentos, tornam-se `PROCEDENTE` ou `IMPROCEDENTE`; vazio ou valor não reconhecido vira `INDETERMINADO`. A taxa de procedência usa somente `PROCEDENTE + IMPROCEDENTE` como denominador. A marca informativa **Revisar responsabilidade** requer pelo menos seis classificações conhecidas e taxa de Improcedentes de 60% ou mais; não afirma falso positivo e não altera o Índice ARION V2.

O drawer inclui resumo, barra proporcional, motivos com contagens de procedentes/improcedentes, dimensões de Projeto/Cliente/UF, links com as duas classificações e chamados paginados em lotes de 10 ou 50. O modal mostra somente campos operacionais do mirror; não inclui artigos, notas internas ou anexos, e contatos reconhecíveis no título são removidos na resposta. Um futuro V3 poderá avaliar ajuste por responsabilidade depois de validação semântica.

## Exportação e navegação para a Base

PDF e XLSX usam a análise e os filtros atuais. Ambos apresentam o Índice ARION V2 e seus cinco pontos componentes. O XLSX mantém as abas **Resumo**, **Ranking**, **Providers**, **Links** e **Tickets** (o cabeçalho em português é “Chamados”). Exportação, detalhe e navegação individual para Base respeitam `LinkQueryService.base(user)`; não há acesso fora do escopo autorizado.

O link individual abre a Base por `config_item_id` exato, resolvido dentro do queryset já limitado por Data Scope. Dimensões herdadas/contraditórias não ampliam o acesso; um ConfigItem fora do escopo não retorna resultado. A ação de lista mantém o filtro do provedor para mostrar os links acessíveis.

## Índice ARION V1 · histórico

A V1 combinava risco proporcional (70%) e impacto absoluto (30%), convertendo os componentes em percentis ordinais do conjunto comparado. Risco proporcional: taxa de links afetados (25%), chamados por 100 links (20%), taxa de reincidência (20%), taxa >24h (20%), backlog por 100 links (10%) e criticidade alta/crítica (5%). Impacto absoluto: chamados (40%), links afetados (30%), chamados >24h (20%) e backlog (10%).

Esse modelo podia atribuir 43,3 a provedores sem ocorrência por causa dos percentis dos empates. Está preservado apenas como metodologia histórica e para o estudo de comparação; não alimenta mais tela, drawer, histórico atual nem exportação.

## Estudo real da mudança

O estudo read-only sobre o snapshot de outubro/2026 registra posições V1/V2, Top 10 das três visões e casos relevantes em `docs/estudos/ARION-RANKINGS-V1-V2-OUTUBRO-2026.md`. O relatório descreve escopo, normalização P95 e limites de interpretação.
## Implementação e interpretação

Campos brutos e classificação de fechamento estão em [OTRS](../OTRS.md); a canonicalização compartilhada e a interpretação de acompanhamento ficam em [Chamados](chamados.md).

A rota `/rankings/` e seus detalhes/exports são implementados no app `rankings`; regra de negócio em `services.py`/`performance.py`, export em `exports.py`, interface em `templates/rankings/` e JavaScript fonte em `frontend_src/js/rankings/`. Visões usam o universo de ticket válido, Data Scope e associação Provider/ISP documentados; filtros mudam recorte, não fórmula.

Índice ARION V2 é indicador operacional comparativo: não é SLA contratual, prova de responsabilidade causal de Provider nem avaliação de qualidade de atendimento externa. Períodos por criação e snapshot de backlog são conceitos distintos. Versão anterior e comparações numéricas em `docs/estudos/` são históricas e não definem o contrato ativo.
