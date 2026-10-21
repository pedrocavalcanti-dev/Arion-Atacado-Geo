# Arion Atacado Geo

## Stack

- Python 3.12
- Django
- SQLite durante desenvolvimento
- HTML, CSS e JavaScript vanilla
- Mapbox GL JS para mapas

## Estrutura

Os apps Django ficam exclusivamente em:

arion_geo/aplicativos/

Templates globais:

arion_geo/templates/

Arquivos estáticos:

arion_geo/static/

O arquivo de gerenciamento Django é:

arion_geo/gerenciar.py

## Front-end

- Não colocar CSS inline.
- Não colocar grandes blocos JavaScript dentro de templates.
- CSS deve ficar em static/css/.
- JavaScript deve ficar em static/js/.
- Reutilizar base.html.
- Utilizar variáveis CSS globais.
- Tema principal dark.
- Interface responsiva.
- Componentes visuais próprios.
- Evitar bibliotecas front-end pesadas sem necessidade.

## Arquitetura

Separar responsabilidades entre os apps.
Evitar lógica de negócio em templates.
Views devem permanecer enxutas.
Preparar services.py quando houver integração externa ou lógica complexa.

## Produto

O sistema representa operações do NOC e NOC Atacado.

Estrutura conceitual:

Operação -> Operadora -> Projeto -> Cliente -> Circuito

Um circuito pode ser fornecido diretamente pela operadora ou através de ISP terceiro contratado pela Arion.

O sistema não é inicialmente um NMS ou ferramenta de monitoramento.
Seu foco inicial é base de links, chamados, análise geográfica e apresentação executiva.
