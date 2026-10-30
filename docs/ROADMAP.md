# Roadmap — próxima release

Revisado em 29/10/2026. A primeira rodada de exposição de Rankings foi implementada localmente. As pendências remanescentes estão marcadas abaixo; esta alteração não prepara release, deploy ou produção. A versão e as notas apresentadas aos usuários ficam em `docs/releases/releases.json` e só são atualizadas ao preparar a próxima versão.

## Foco inicial: evolução de Rankings

A tela existente de Rankings recebeu a visão **Mais links** como primeira perspectiva, mantendo as visões de risco, melhor desempenho e sem ocorrências. O **Índice ARION V2** e seu cálculo continuam preservados; os novos indicadores de exposição são mostrados em separado.

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

## Decisões de dados adotadas

- **Link ativo:** `CMDBLinkMirror.is_present_in_source=True` e implantação `Operacional` ou `Operational`. No snapshot local de 29/10/2026 há 3.194 links operacionais, 251 cancelados e 1 em manutenção. Estados vazios ou não reconhecidos não entram.
- **Origem da exposição:** agregação atual em CMDB por `CMDBLinkMirror.operator`, cuja resolução usa ConfigItemID ou nome único exato. Não usa fuzzy matching, nomes hardcoded nem ID técnico como nome.
- **Denominador e período:** links são snapshot atual; chamados são contados pela criação no período. A interface e a documentação explicitam essa diferença, inclusive na visão de 12 meses.
- **Reuso da taxa atual:** a página já documenta Chamados por Link. Auditar o cálculo e reutilizá-lo; a nova apresentação por 100 links deve ser escala/formatação consistente da mesma taxa, sem criar uma segunda definição incompatível.
- **Histórico do inventário:** sem snapshots históricos da CMDB, a taxa histórica usa o denominador atual e precisa dizer isso. Se houver snapshots no futuro, avaliar a comparação de links ativos e chamados no mesmo mês.
- **Granularidade de evidência:** deduplicar tickets por provedor segundo as regras de Ranking atuais e explicar quando um ticket associado a vários provedores conta uma vez em cada linha. Preservar o total nacional distinto e sua diferença para a soma das linhas.
- **Limite mínimo de Links:** Todos por padrão; filtros opcionais 10+, 30+, 50+ e 100+. Provedores pequenos continuam visíveis sem o filtro.
- **Filtros:** avaliar Projeto, Cliente, UF, Operadora/Provedor e Período, respeitando permissões, Data Scope e as dimensões disponíveis. A combinação deve continuar sendo a interseção aplicada pelo backend.
- **Indicadores internos:** ANOP e ETIT seguem sem definição comprovada. A busca nos documentos encontrou somente pendências; os campos armazenados nos mirrors locais não têm esses tokens e o banco não possui linhas Claro importadas. Não foram implementados.

## Plano de trabalho

1. [x] Auditar tela, serviço, filtros, exportações e Data Scope; reutilizar os padrões existentes.
2. [x] Definir link ativo a partir do estado de implantação CMDB e validar a distribuição local.
3. [x] Usar a entidade CMDB resolvida por ConfigItemID ou nome único exato, sem fuzzy matching.
4. [x] Criar a visão Mais links, com Top 20 padrão e opções 10/20/30/50/Todos.
5. [x] Mostrar chamados absolutos e contexto ativo sem substituir o cálculo ARION V2.
6. [x] Calcular Chamados por 100 links ativos atuais e explicar a janela temporal.
7. [x] Preservar provedores pequenos e tornar o mínimo de links um filtro opcional.
8. [x] Reutilizar filtros de Cliente, Projeto, Provedor, UF e período sob Data Scope backend.
9. [ ] Confirmar ANOP/ETIT com a área responsável; não há definição nos dados locais revisados.
10. [x] Incluir backlog, >24h e tempo médio de tickets encerrados no período; não incluir SLA sem regra comparável validada.
11. [x] Validar contagem agrupada no banco, filtro de escopo e testes focados.
12. [x] Integrar a visão de exposição à página atual sem redesenho e manter as três visões existentes.
13. [x] Atualizar a documentação funcional e registrar limitações. As notas da release ficam para o preparo de uma versão.

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

## Estado da implementação local

A visão usa somente mirrors locais; nenhuma migration foi necessária e o OTRS remoto não é consultado durante a abertura da tela. A validação focada foi executada com banco SQLite de teste porque o usuário MySQL local não pode criar o banco temporário de testes. O `check` do Django passou. ANOP/ETIT e eventual comparação com regra contratual específica de provedor seguem pendentes de validação de negócio.
