# Mapa

O Mapa e a visao geografica operacional do NOC Atacado. A interface oferece os modos Base, Projetos, Chamados, Reincidencia e Motivos, com filtros compartilhados de cliente, projeto e provedor. O painel Brasil mostra resumo contextual, ranking Top 5 e distribuicao; selecionar uma UF abre detalhes com bandeira local, links, tickets e dimensoes relacionadas.

## Fontes e dimensoes

O backend consulta somente os mirrors locais. `CMDBLinkMirror.name` preserva o Nome original do CMDB. `LinkBusinessIdentityService` deriva Cliente/operadora contratante, Projeto, Conta e Business ID somente de prefixos reconhecidos e delimitadores estruturados. Separadores (`-`, en dash e em dash), espacos e acentuacao sao normalizados para comparacao, sem substituir o texto raw. Classificacoes ambiguas ficam vazias. `legacy_project` continua historico e nao e o Projeto principal.

Cliente/Projeto/Conta sao dimensoes comerciais parseadas do nome CMDB por `BusinessIdentityRules`. TELMEX e preservado como valor raw, mas sua dimensao Cliente canonica e Claro. Provedor/ISP e sempre o `CMDBLinkMirror.operator` associado ao ConfigItem; nao se mistura com Cliente.

O Data Scope e aplicado por `LinkQueryService.base(user)` antes de filtros, catalogos, detalhes ou agregacoes. Operadora de escopo representa Cliente/contratante e Projeto representa `business_project`. Para grupos antigos, `legacy_project` so e consultado quando o link ainda nao tem Projeto parseado, preservando a intersecao sem alargar o acesso de links classificados.

## Modos e datas

- Base e Projetos sao o snapshot CMDB atual; nao usam periodo.
- Chamados contam tickets distintos relacionados a links da UF, pela data local de criacao (`source_created_at`), nos estados `OPEN`, `PENDING`, `SCHEDULED`, `RESOLVED` e `CLOSED`. `CANCELED` e `UNKNOWN` ficam fora. Um ticket relacionado a varios links na mesma UF conta uma vez nessa UF e uma vez no total nacional. Links afetados sao distintos por UF e no total.
- Reincidencia conta links com ao menos dois tickets distintos validos criados no periodo; tickets nos links reincidentes tambem sao apresentados.
- Motivos contam encerramentos `RESOLVED`/`CLOSED` pela data local `terminal_state_at`, usando `closing_code_raw` e o normalizador compartilhado do Cockpit. Tickets cancelados, sem codigo de encerramento ou sem data terminal nao entram.

Os limites de data usam inicio inclusivo e dia seguinte exclusivo no fuso local, evitando conversoes `DATE()` inconsistentes entre SQLite e MySQL. Periodos disponiveis: este mes, mes anterior, ultimos 30/90 dias e intervalo personalizado.

## Mapa e API

A representacao e choropleth estadual com as 27 UFs do asset local `static/geo/brasil_estados.geojson`; nao existem coordenadas confiaveis por link e nao ha geocodificacao/markers individuais. Em Base/Projetos, a cor indica o Cliente predominante na UF (Claro terracota, Vivo roxo, Algar verde, demais neutro); ao filtrar um cliente, a intensidade representa volume. Chamados, Reincidencia e Motivos usam escalas quantitativas separadas. Hover mostra a metrica do modo e clique abre o drawer da UF.

`GET /base/api/mapa/` agrega links e tickets no backend e retorna contagens por UF, sem enviar tickets ou links completos ao navegador. Parametros: `mode`, `client`, `project`, `provider`, `period`, `date_from`, `date_to`, `reason`, `status` e `priority` quando aplicaveis. O detalhe e servido em `GET /base/api/mapa/uf/` com `uf` e os mesmos filtros; lista apenas os links correspondentes ao recorte selecionado, com limite e indicacao de truncamento. A integracao para Base usa filtros de UF/cliente/projeto/provedor; a integracao para Cockpit usa UF, metrica, periodo e motivo quando aplicavel.

O Mapbox recebe as geometrias estaduais e os valores agregados. O token e publico por definicao do SDK e vem de `MAPBOX_PUBLIC_TOKEN`; sem token ou sem rede, a pagina informa o erro recuperavel sem apagar o restante da aplicacao. Bandeiras sao assets locais em `static/imagens/bandeiras/estados/`.

## Qualidade da identificacao de negocio

Snapshot do mirror local: 3.437 links. Antes das regras comerciais confirmadas, Cliente estava identificado em 2.074 (60,34%) e nao identificado em 1.363 (39,66%). Depois da reclassificacao derivada, 3.057 (88,94%) estao identificados e 380 (11,06%) permanecem sem inferencia. Projeto identificado: 3.197 (93,02%); Provedor/ISP permanece em 97,03%. As proporcoes pertencem ao snapshot consultado e variam com a sincronizacao.

Nos 1.363 links sem Cliente, nomes/prefixos recorrentes incluem BANCO DO BRASIL (338), FUST (307), BRADESCO (152), ARCOS DOURADOS (105), CAIXA ECONOMICA FEDERAL (65), CORREIOS (45), FUST UBS (45), ESCOLAS CONECTADAS (43), LINK MOTIVA (32), DIVERSOS (27) e SANTANDER (15). Esses prefixos nao identificam, por si, o cliente contratante. O ISP tambem varia dentro desses grupos. Nenhuma regra Cliente foi inferida deles. O parser ja reconhece um segmento de projeto imediatamente antes de um Business ID delimitado; os prefixos com segmentos adicionais continuam ambiguos e nao foram promovidos a Projeto nesta revisao. Nenhum dado do CMDB de origem foi alterado.

TELMEX e um token comercial explicito relacionado a operacao Claro: o raw continua auditavel no nome CMDB e em `contracting_client_raw`, enquanto `contracting_client` e canonico Claro. `Outras` agrupa clientes identificados fora de Claro/Vivo/Algar; Cliente nao identificado e uma categoria separada no resumo e na legenda. Se a categoria nao identificada for maior que qualquer categoria identificada agregada, a UF recebe o tom neutro.

Na apresentacao por UF, Cliente, Projeto, Conta e Provedor usam rotulos de nao identificacao especificos da dimensao. O drawer Base informa cobertura de Cliente e as quantidades identificada/nao identificada. Variantes de cidade sao agrupadas por chave sem acento, caixa e espacos; o nome de origem permanece intacto. No snapshot estudado, Goiânia/GOIANIA em GO soma 14 links sob o rotulo Goiânia. Rotulos de Projeto amigaveis sao apenas de exibicao; filtros mantem a chave persistida.

Base e Projetos sao snapshots CMDB e nao exibem Periodo. Chamados, Reincidencia e Motivos exibem Periodo e aceitam `YYYY-MM` em URLs compartilhaveis. A URL do Mapa preserva modo, cliente, projeto, periodo, UF, motivo e provedor. As secoes do drawer dependem do modo e de haver dados; Motivos nao aparece na Base.


## Regras comerciais e contexto OTRS

`BusinessIdentityRules` centraliza a precedencia: cliente explicito no nome CMDB; regra de projeto exclusivo; projetos compartilhados sem inferencia; caso ambiguo sem cliente. TELMEX canoniza para Claro, Telefonica/Vivo para Vivo; Correios, Banco do Brasil, Caixa Economica Federal e Carrefour inferem Claro; Fust, L2L e Arcos Dourados/McDonald's inferem Vivo; Escolas Conectadas infere Algar. Bradesco e Diversos nunca inferem cliente sozinhos. O Nome original CMDB permanece intacto e campos derivados do mirror foram recalculados; a origem CMDB nao foi alterada. Nomes regionais `Claro.al`, `Claro.mt` e `Claro.pr` permanecem distintos.

O catalogo de projetos foi reduzido de 64 rotulos raw parseados para 52 grupos canonicos, unificando 12 variantes confirmadas; nomes regionais sem regra permanecem intactos.

`TicketBusinessIdentityService` interpreta o titulo espelhado do ticket para contexto do proprio ticket (cliente, projeto, tipo, servico e Business ID). Cliente explicitamente confiavel do titulo prevalece no contexto analitico do chamado; na ausencia dele, usa-se a identidade do link CMDB. Essa classificacao nao atualiza o link. No snapshot analisado, 10.195 de 11.973 titulos continham ao menos um campo de identidade reconhecido (9.442 com cliente e 5.149 com projeto). O drawer autorizado do Mapa apresenta titulo, status, prioridade, datas, motivo, identidade parseada e campos operacionais do ConfigItem; artigos, notas internas, anexos e dados pessoais nao sao importados nem apresentados. Chamados distribui tickets por status, motivo, cliente, projeto ou provedor em um unico painel e o detalhe do ticket abre modal acessivel.
