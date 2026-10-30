# Diretrizes de Interface

## Princípios visuais

Preservar a identidade aprovada do Arion: interface corporativa, clara, espaçada e com hierarquia consistente. Usar bordas suaves, sombras discretas, ícones pequenos e poucos elementos decorativos. Evitar excesso de cards, badges, gradientes e componentes sem propósito.

## Temas e componentes

Novas telas devem reutilizar tokens e variáveis CSS existentes e funcionar em tema claro e escuro. A preferência persistida do usuário é a fonte principal do tema. Manter CSS e JavaScript separados dos templates sempre que possível; usar HTML semântico e componentes reutilizáveis quando houver padrões compartilhados.

Formulários devem manter labels claras, alinhamento consistente, foco visível e controles compatíveis com o design do produto. Evitar controles nativos crus em áreas administrativas quando já houver componente visual do projeto.

## Dados e feedback

Indicadores precisam explicitar contexto e fonte quando necessário. Marcar claramente dados REAL e DEMO; métricas simuladas nunca devem parecer oficiais. Páginas devem prever estados de carregamento, vazio, sucesso e erro sem apresentar exceções técnicas ao usuário.

## Responsividade e acessibilidade

Viewports de referência: 1920×1080, 1440×900, 1366×768, 1024×768, 768 px e 390 px. Evitar overflow horizontal global; em tabelas largas, limitar rolagem ao contêiner apropriado. Componentes devem ter foco perceptível, labels, navegação por teclado e atributos ARIA quando aplicáveis. Não comunicar estado apenas por cor.

## Visualização de dados

Gráficos, mapas e rankings devem preservar legibilidade, unidade e período. Percentuais e scores devem ter contexto e origem; dados demonstrativos precisam de identificação visível. Reutilizar padrões existentes em vez de introduzir um sistema visual paralelo.
## Central de Documentação

A Central (`templates/documentacao/` e `static/css/documentacao.css`) usa o design system existente, a preferência persistida de tema e categorias recolhíveis. Manter visível a identidade **ARION OPS · NOC ATACADO** sem criar um tema paralelo. O portal é server-rendered e seu renderer Markdown permite apenas um subconjunto seguro; conteúdo HTML bruto é escapado.

Diagramas são inline SVG gerados localmente a partir do subconjunto de fluxogramas Mermaid usado nos documentos. Notas tipadas são callouts semânticos com cores discretas. Em tema claro/escuro, reutilizar tokens `--docs-*` mapeados a tokens globais; não introduzir biblioteca de diagramas ou syntax highlighter pesado.

A navegação deve permanecer agrupada/recolhível; home e busca contam documentos do registry em tempo de renderização. Sidebar recolhe em viewport estreita; tabelas/código rolam dentro de seus contêineres; âncoras e índice precisam permanecer navegáveis por teclado. Ao adicionar um Markdown, registre title, description, category, search terms e caminho permitido no registry, crie link na home/documentação e inclua testes de rota, busca e links.


## Identidade visual ARION OPS

O nome visual do produto é **ARION OPS**; ARION é a empresa e NOC ATACADO é o contexto operacional. A marca usa `#00BF9A` (verde), `#FF8440` (laranja) e `#6D6E71` (cinza), centralizadas nos tokens de `static/css/base.css`; os componentes compartilhados são ajustados por `static/css/branding.css`. Usar `static/branding/arion/` para as versões principal, clara e monocromática do logotipo, `static/branding/symbols/` para símbolos oficiais, `static/favicon/` para favicons e `static/pwa/` para ícones, manifesto e experiência PWA. Usar o logotipo claro em fundo escuro e o principal em fundo claro.

O header autenticado usa a logo ARION OPS unificada: `arion-ops-logo-light.png` no tema escuro e `arion-ops-logo-primary.png` no tema claro, em `static/branding/arion/`. Se uma variante não carregar, o header mantém como fallback as logos ARION antigas com o texto OPS separado.

Padrões geométricos discretos podem usar triângulos e recortes diagonais em CSS, com baixa opacidade do verde ARION e do cinza. A implementação compartilhada fica em `static/css/branding.css`; use modificadores apenas nas áreas vazias aprovadas de fundo/cabeçalho, fora de cards, gráficos, tabelas e mapas. No Mapa, qualquer detalhe fica no cabeçalho antes da área geográfica. Pseudo-elementos decorativos usam `pointer-events: none` e são reduzidos/ocultos em telas estreitas. O padrão deve permanecer sutil nos temas claro e escuro.

O crédito institucional aparece em **Sobre o ARION OPS** e em `NOTICE.md`, não no header nem em cards operacionais. ARION OPS foi concebido e desenvolvido por Pedro Cavalcanti para apoio às operações do NOC Atacado da ARION.

## Login e atualizações PWA

Preservar a composição institucional aprovada do login ARION OPS e manter a autenticação livre de avisos de versão. O carrossel pode receber ajustes pontuais de espaçamento e vidro translúcido sem mudar sua estrutura. O aviso de release deve ser compacto, legível nos temas claro e escuro e usar o verde ARION como detalhe. Depois fecha o aviso da versão pendente e deixa o indicador global acessível sem reapresentar o toast a cada navegação; uma nova versão deve voltar a ser sinalizada.
