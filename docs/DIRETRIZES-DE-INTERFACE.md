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

A Central (`templates/documentacao/` e `static/css/documentacao.css`) usa o design system existente, a preferência persistida de tema e categorias recolhíveis. Manter visível a identidade **ARION ATACADO GEO · NOC ATACADO** sem criar um tema paralelo. O portal é server-rendered e seu renderer Markdown permite apenas um subconjunto seguro; conteúdo HTML bruto é escapado.

Diagramas são inline SVG gerados localmente a partir do subconjunto de fluxogramas Mermaid usado nos documentos. Notas tipadas são callouts semânticos com cores discretas. Em tema claro/escuro, reutilizar tokens `--docs-*` mapeados a tokens globais; não introduzir biblioteca de diagramas ou syntax highlighter pesado.

A navegação deve permanecer agrupada/recolhível; home e busca contam documentos do registry em tempo de renderização. Sidebar recolhe em viewport estreita; tabelas/código rolam dentro de seus contêineres; âncoras e índice precisam permanecer navegáveis por teclado. Ao adicionar um Markdown, registre title, description, category, search terms e caminho permitido no registry, crie link na home/documentação e inclua testes de rota, busca e links.
