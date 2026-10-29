# Roadmap — próxima release

Revisado em 29/10/2026. Este documento planeja trabalho futuro; os itens abaixo não foram implementados nesta rodada. A versão e as notas apresentadas aos usuários ficam em `docs/releases/releases.json`; o procedimento de release está em [Implantação e Produção](IMPLANTACAO-E-PRODUCAO.md#versionamento-e-notas-de-release). Mudanças locais só entram nas notas quando a próxima versão for preparada.

## Foco inicial: evolução de Rankings

A próxima frente é evoluir a tela existente de Rankings, com prioridade para Rankings de Provedores. Neste roadmap, “Rankings V2” identifica essa próxima rodada de produto. O **Índice ARION V2** e o ranking absoluto já existentes continuam ativos e devem ser preservados; o novo trabalho adiciona perspectivas complementares sem substituir a página inteira.

### Perguntas que a evolução deve responder

- Quais provedores têm maior participação/exposição na operação?
- Quais geram mais chamados em números absolutos?
- Quais geram mais chamados proporcionalmente à quantidade de links?
- Quais concentram backlog ou maior tempo de resolução?
- Quais merecem maior cobrança operacional ou comercial, com indicadores confiáveis?

### Perspectivas planejadas

1. **Exposição / volume de links:** Top 10 provedores por quantidade de Links da Base CMDB, usando nomes resolvidos da entidade Provider/ISP e sem dados hardcoded.
2. **Chamados absolutos:** manter o ranking atual de quantidade de chamados/problemas; número absoluto continua sendo uma resposta válida e não pode ser removido.
3. **Incidência proporcional:** comparar Links e Chamados por provedor e apresentar `Chamados por 100 links = (chamados / links) × 100`.
4. **Provedor pequeno com alta incidência:** preservar a capacidade de identificar casos como um Link com vários problemas; volume baixo não deve esconder uma taxa alta.
5. **Backlog e desempenho:** avaliar backlog, tempo médio de resolução, tickets acima de 24h e SLA apenas onde a fonte e a regra forem confiáveis.

O resultado deve oferecer as duas leituras em conjunto: **VOLUME / EXPOSIÇÃO** e **QUALIDADE / INCIDÊNCIA**. Não criar score composto até que suas variáveis e pesos tenham validação de negócio.

Hoje, a visão **Sem ocorrências** já pode ordenar até 10 provedores pelo número de Links, mas inclui somente provedores sem chamados nem backlog. A nova visão de Exposição deve cobrir todos os provedores elegíveis do recorte, sem duplicar ou substituir esse uso existente.

## Contratos de dados a fechar antes da implementação

- **Link ativo:** identificar o campo real da CMDB/Base Links e acordar a regra operacional. Excluir desativados, cancelados e duplicados somente se os dados e a regra confirmarem que não pertencem ao estoque ativo. Não escolher um campo por suposição.
- **Origem da exposição:** contar Links atuais da CMDB/Base Links, não inferir inventário pela quantidade de tickets. O nome do provedor deve vir da relação Provider/ISP resolvida; não usar ID técnico como nome nem hardcodear catálogo.
- **Denominador e período:** Links atuais são um snapshot; Chamados são fluxo do período escolhido. A interface deve rotular claramente, por exemplo, “Links ativos atuais” e “Chamados nos últimos 30 dias”. Não descrever a taxa como se o inventário de links fosse histórico.
- **Reuso da taxa atual:** a página já documenta Chamados por Link. Auditar o cálculo e reutilizá-lo; a nova apresentação por 100 links deve ser escala/formatação consistente da mesma taxa, sem criar uma segunda definição incompatível.
- **Histórico do inventário:** sem snapshots históricos da CMDB, a taxa histórica usa o denominador atual e precisa dizer isso. Se houver snapshots no futuro, avaliar a comparação de links ativos e chamados no mesmo mês.
- **Granularidade de evidência:** deduplicar tickets por provedor segundo as regras de Ranking atuais e explicar quando um ticket associado a vários provedores conta uma vez em cada linha. Preservar o total nacional distinto e sua diferença para a soma das linhas.
- **Limite mínimo de Links:** analisar a distribuição real antes de escolher limites ou defaults. Considerar uma opção como Todos / mínimo de Links, mas não fixar agora valores como 10, 20 ou 30 sem evidência.
- **Filtros:** avaliar Projeto, Cliente, UF, Operadora/Provedor e Período, respeitando permissões, Data Scope e as dimensões disponíveis. A combinação deve continuar sendo a interseção aplicada pelo backend.
- **Indicadores internos:** validar o significado e a regra de cálculo de ANOP, ETIT e outros termos operacionais em fontes internas antes de implementar. A busca atual no código e em `docs/` não encontrou definição comprovada; não presumir significados.

## Plano de trabalho

1. Auditar a tela atual de Rankings, serviços, dados, exports e Data Scope; mapear os componentes e cálculos que devem ser reutilizados.
2. Mapear Base Links/CMDB e definir, com evidência, a regra de Link ativo.
3. Conferir e consolidar o nome canônico dos provedores, preservando variações de negócio que não sejam equivalentes.
4. Criar Top 10 por quantidade de Links como uma perspectiva de exposição.
5. Cruzar quantidade de Links e chamados por provedor sem alterar o ranking absoluto existente.
6. Calcular e apresentar Chamados por 100 links, deixando claro o snapshot atual do denominador e o período dos chamados.
7. Preservar a leitura de provedores pequenos com alta incidência e avaliar limite mínimo usando a distribuição real.
8. Avaliar filtros de Projeto, Cliente, UF, Provedor e Período conforme disponibilidade e Data Scope.
9. Validar ANOP, ETIT e demais indicadores com responsáveis/fontes internas.
10. Avaliar backlog, tempo médio por provedor, tickets acima de 24h e SLA individualmente quanto à confiabilidade.
11. Validar unicidade, escopo, consistência com Base/Cockpit, consultas e performance.
12. Refinar a interface sem redesenhar a página toda: usar uma alternância/tabs como Exposição, Incidência, Backlog e Desempenho para evitar vários rankings longos ao mesmo tempo.
13. Registrar limites e fontes dos indicadores, atualizar documentação técnica e notas da release somente quando a implementação for fechada para publicação.

## Princípios de UX

- Preservar a estrutura atual e os rankings absolutos aprovados.
- Não colocar várias listas extensas na mesma tela; usar seletor/abas ou uma alternância equivalente.
- Exibir links, chamados e taxa juntos quando isso facilitar a comparação entre exposição e incidência.
- Sinalizar período de chamados e data/snapshot dos Links.
- Distinguir taxa alta com base pequena de volume absoluto alto; não ocultar nenhum dos dois casos.
- Manter a página responsiva, clara/escura e consistente com o design aprovado do ARION.

## Limitações e dívidas conhecidas

- A CMDB operacional disponível representa o estado atual; não há série de snapshots históricos documentada para construir denominadores históricos de Links.
- Os eventos `Move` e `StateUpdate` do OTRS permitem estudar transições, mas o mirror ainda não persiste a sequência completa por ticket. Não há duração histórica confiável por etapa no Cockpit nem métrica pronta por etapa para Rankings.
- No Cockpit, Novos usa `source_created_at`; por isso não mede quando um ticket foi movido para uma fila ou entrou no processo de Cancelamentos. Avaliar a materialização de eventos de fila antes de definir uma métrica histórica de entrada operacional.
- A série histórica de backlog do Cockpit depende de datas confiáveis e reconciliação com o snapshot atual. Ela não recompõe todos os ciclos de reabertura ou mudanças de fila.
- A marca de 24 horas é referência operacional do ARION, não confirmação de SLA contratual. SLA só pode entrar no ranking com regra/fonte formal validada.
- Tickets sem Provider resolvido e tickets associados a mais de um Provider afetam a cobertura e a soma das linhas; preservar as regras e explicações documentadas em [Rankings](funcionalidades/rankings.md).
- UNKNOWN em Cancelamentos é uma condição real de classificação/cobertura e precisa permanecer visível, não ser convertido automaticamente em uma das etapas.
- ANOP e ETIT seguem sem definição comprovada nos materiais revisados; suas fórmulas não devem ser inventadas.

## Fora do escopo desta rodada documental

Não houve alteração da tela de Rankings, fórmula do Índice ARION V2, filtros, modelos ou dados. Esta rodada registra requisitos, perguntas e decisões pendentes para a próxima release; a implementação deve começar após a auditoria dos dados e a validação da regra de Link ativo.
