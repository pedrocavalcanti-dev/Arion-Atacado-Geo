# Base de Links

A página Base consulta somente `CMDBLinkMirror` presente na fonte, com o provedor resolvido por `CMDBOperatorMirror`. Requests não leem XLSX nem fazem chamadas ao serviço CMDB. O queryset passa pelo `DataScopeService` antes de busca, filtros, contagens, paginação e exportação.

## Semântica exibida

- **Designação** usa `designation`; se estiver vazia, apresenta `name` e depois `source_number`.
- **Projeto legado** apresenta `legacy_project`, um valor histórico congelado da antiga base XLSX; vazio fica como `Não classificado`. A Base não atualiza esse campo.
- **Operadora contratada** permanece `Não classificada` porque não há campo ou relação oficial confirmada no mirror.
- **Provedor** é o nome da entidade CMDB associada ao Link. Sem entidade resolvida, apresenta `Não classificado`; `isp_raw` fica no detalhe técnico.
- Estados de implantação e incidente vêm dos estados CMDB. Incidente não é inferido de Tickets.

Os KPIs contam Links presentes, estado de implantação operacional, estado CMDB `Incident`, estado de implantação cancelado e entidades de Provedor distintas associadas aos Links presentes. Provedores sem Link não entram nessa contagem.

## Busca, filtros e paginação

A busca combina termos por designação, Name, Number, ConfigItemID, circuito, endereço, cidade, UF, contrato, projeto, provedor e ISP original. Ela é executada no banco com normalização de acentos e caixa; múltiplos espaços da consulta são tratados como separadores. Identificadores permanecem sem reescrita. Projeto, Provedor, UF, implantação, incidente e tipo são filtros independentes. Não há filtro de Operadora contratada enquanto essa dimensão não tiver fonte confiável.

A lista usa paginação server-side, 50 itens por padrão e opções de 25, 50, 100 ou 200. Filtros permanecem na URL e na navegação entre páginas. A rolagem horizontal, quando necessária, fica limitada à tabela.

## Detalhe e exportação

O drawer consulta os dados persistidos no Arion por uma única rota local; abrir o detalhe não chama o CMDB. Mostra primeiro relação de negócio, localização e dados do Link; identificadores e versão ficam em Dados CMDB. Segredos PPOE não fazem parte do mirror e não são exibidos. O CSV aplica os mesmos filtros e Data Scope da lista e exporta as dimensões sem credenciais.

O acesso à lista/catálogo de Provedores é derivado das entidades CMDB que possuem Links presentes. A tela do catálogo pagina os resultados e informa ConfigItemID, Number CMDB e quantidade de Links associados.

Models e serviços XLSX legados permanecem no código para rollback, mas não participam do caminho da Base.
