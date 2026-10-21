
# Arion Atacado Geo

Plataforma interna de inteligência geográfica e operacional do NOC Atacado da Arion.

## Objetivo

Centralizar e visualizar:

- base de links;
- operadoras;
- projetos;
- clientes;
- ISPs terceiros;
- chamados;
- reincidências;
- motivos de encerramento;
- indicadores geográficos;
- relatórios executivos.

## Stack

- Python 3.12
- Django 5.2
- SQLite no desenvolvimento
- Mapbox GL JS
- HTML
- CSS
- JavaScript

## Desenvolvimento

````powershell
.\.venv\Scripts\Activate.ps1
cd arion_geo
python gerenciar.py runserver
```

Abra [http://127.0.0.1:8000/](http://127.0.0.1:8000/). A raiz encaminha para o login ou para o mapa conforme a sessão. O endereço `/admin/` continua disponível para administração.

## Configuração

O projeto inicia em desenvolvimento sem exigir um arquivo `.env`. Para personalizar a configuração, copie `env-example` para `.env` na raiz do repositório e defina `DJANGO_SECRET_KEY`, `DJANGO_DEBUG` e `DJANGO_ALLOWED_HOSTS`. Use uma chave secreta própria em qualquer ambiente compartilhado ou de produção. O arquivo `.env` não deve ser versionado.

## Mapbox

Defina `MAPBOX_PUBLIC_TOKEN=` no `.env` local para habilitar o mapa. O token é lido do ambiente e exposto somente ao cliente Mapbox. Sem ele, a tela informa que o serviço não está configurado. Os polígonos locais em `arion_geo/static/geo/brasil_estados.geojson` foram normalizados do [GeoJSON de estados do projeto br-geojson](https://github.com/henriquemalvar/br-geojson/tree/main/dist), que usa as [Malhas Territoriais do IBGE](https://servicodados.ibge.gov.br/api/v4/malhas/paises/BR?formato=application/vnd.geo%2Bjson&qualidade=minima&intrarregiao=UF) e a [API de Localidades do IBGE](https://servicodados.ibge.gov.br/api/v1/localidades/estados). O arquivo é servido localmente, sem buscar geometrias externas durante o uso.

## Bandeiras das Unidades Federativas

As 27 bandeiras estaduais (e do Distrito Federal) em formato SVG estão armazenadas localmente em `arion_geo/static/imagens/bandeiras/estados/` (`ac.svg` a `to.svg`) e não dependem de requisições externas em tempo de execução. Os arquivos oficiais têm origem no [Wikimedia Commons — categoria *SVG flags of states of Brazil*](https://commons.wikimedia.org/wiki/Category:SVG_flags_of_states_of_Brazil), distribuídos em domínio público (símbolos oficiais brasileiros).

## Rotas desta etapa

- `/login/` - autenticação Django por usuário e senha.
- `/logout/` - encerra a sessão por requisição POST protegida por CSRF.
- `/mapa/` - mapa autenticado do Brasil com filtros demonstrativos por operadora.
- `/dashboard/` - dashboard executivo autenticado com indicadores e evolução demonstrativa.
- `/rankings/` - ranking executivo autenticado de 20 provedores com dados demonstrativos, filtros e critérios de ordenação. A leitura fica isolada em `aplicativos.rankings.services`, pronta para substituir a fonte JSON por uma integração real.
- `/painel/` - visão geral autenticada.
- `/admin/` - Django Admin.

O mapa, integrações externas, dados operacionais e importação de planilhas pertencem a etapas posteriores.



## Dados temporais demonstrativos do mapa

A experi?ncia do mapa consome agregados locais em `arion_geo/static/data/demo/`: `base.json` guarda links por operadora/projeto/UF, `history.json` guarda links, chamados, reincid?ncias e motivos por compet?ncia, e `projects.json`/`reasons.json` descrevem dimens?es. O hist?rico determin?stico cobre jan/26 a out/26; os motivos particionam exatamente os chamados e reincid?ncias nunca superam chamados. `static/js/mapa/mapa-data.js` oferece a interface `load`/`aggregate` que desacopla a tela dos arquivos. Uma futura fonte pode preservar esse contrato com endpoints como `/api/geo/summary/`, `/api/geo/states/`, `/api/geo/state/SP/` e `/api/geo/history/`; nenhum endpoint ou integra??o real est? implementado nesta etapa.
