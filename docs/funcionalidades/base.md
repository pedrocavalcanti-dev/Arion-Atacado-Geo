# Base

A Base reúne duas visões da mesma fonte operacional: **Links de Internet** e **Provedores / ISP**. A visão padrão continua sendo Links; `?view=links` e `?view=providers` preservam a seleção na URL. A origem CMDB chama a classe relacionada aos links de **Operadoras**; no ARION essa relação representa o Provider/ISP do link. Cliente é outra dimensão, derivada do nome original do link, e não é misturada ao Provider.

As telas usam exclusivamente `CMDBLinkMirror`, `CMDBOperatorMirror` e os espelhos locais OTRS. Requisições HTTP não acessam CMDB nem OTRS diretamente. O `DataScopeService` limita primeiro os links; listagens, busca, detalhes de links e providers, relações e tickets são derivados desse conjunto. Um provider sem links presentes e visíveis não aparece.

## Links de Internet

A listagem preserva os filtros de Cliente, Projeto, Provider/ISP, UF, implantação, incidente e tipo, busca, exportação CSV e navegação direta por `config_item_id`. A paginação server-side oferece 25, 50, 100, 200 e 300 itens; padrão 50. A tabela pode rolar horizontalmente e não possui altura/rolagem vertical própria, deixando o wheel vertical para a página.

Colunas: Designação, Cliente, Projeto, Provider, Cidade/UF, Velocidade, Implantação e Incidente. Os estados são os do Link CMDB e não são inferidos de tickets. O drawer carrega os detalhes sob demanda e mantém o cabeçalho fixo enquanto o corpo rola.

## Provedores / ISP

A visão de Providers pertence à página Base e permite buscar por nome, telefone, WhatsApp, CNPJ e ConfigItemID. A tabela mostra telefone (ou WhatsApp quando for o único contato), horário, quantidade de links, estados da entidade Provider e horário do último sync local. A última atualização disponível no mirror é `source_synced_at`; ela representa sincronização, não a data da última alteração na origem.

O drawer do Provider carrega sob demanda seus contatos cadastrados, dados cadastrais, status da entidade, até 20 links associados e resumo operacional local: links totais, links operacionais, links com incidente, tickets da fila NOC nos últimos 30 dias, backlog e links reincidentes. Não mostra índice ARION. As ações abrem os links filtrados por Provider ou o Provider correspondente em Rankings. A exportação CSV de Providers contém apenas nome, contatos de operação, horário, CNPJ, quantidade de links e estados CMDB.

## Contatos e segurança

O sync CMDB mapeia campos operacionais seguros da classe Operadoras: telefone, WhatsApp, horário de atendimento, e-mails de abertura/acompanhamento, URL de portal, CNPJ e categoria. Campo vazio permanece sem informação; não se inventam contatos. A API do drawer seleciona explicitamente esses campos e nunca serializa dados de autenticação.

No snapshot conferido diretamente na CMDB em 24/10/2026 havia 1.330 Operadoras. Considerando valores não vazios e excluindo placeholders como `N/A`, a cobertura era: telefone 1.326, WhatsApp 1.019, horário 1.310, e-mail de abertura 579, e-mail de acompanhamento 34, portal 46, CNPJ 1.184 e categoria 4. Estados de implantação/incidente estavam preenchidos em 1.330. A origem não forneceu `ChangeTime`/timestamp de atualização mapeável; a Base apresenta a data do último sync local em vez de atribuí-la à origem. O FULL dry-run leu as 1.330 Operadoras e 3.437 Links e encontrou os mirrors inalterados.

Credenciais de portal existentes na origem CMDB não são persistidas nem expostas pelo ARION. O nome de usuário de portal foi removido do mirror; a senha e atributos sensíveis continuam filtrados pelo sanitizador do client. Valores de autenticação não são colocados em log, tabela, API ou CSV. O link do portal só é criado para URLs HTTP/HTTPS.

Na leitura de cobertura da origem foram encontrados 9 registros com nome de usuário de portal e 8 com senha de portal. O sanitizador substitui esses valores por marcadores de presença durante o processamento e eles não são mapeados para o mirror; a migration removeu a coluna antiga de nome de usuário.

## Histórico operacional do Link

Ao abrir o drawer, a Base consulta apenas o mirror local: Link → ConfigItemID → `OTRSTicketConfigItem` → `OTRSTicket`. Relações repetidas ao mesmo ticket são deduplicadas. O período selecionável é 30 dias, 90 dias ou 12 meses; o resumo mostra chamados, backlog atual, reincidência e aging operacional >24h. Uma tendência mensal compacta cobre seis meses e a lista exibe dez tickets por página, ordenados por criação decrescente. Tickets não alteram os estados CMDB do Link.

Os tickets usam a fila `NOC - ATACADO`, precisam estar presentes no espelho e ter estado operacional válido. O badge `ARION >24h` é uma medida operacional e não substitui SLA contratual. A classificação de responsabilidade Procedente/Improcedente é apenas apresentada quando disponível e não altera as métricas do Link. O ticket abre um detalhe modal com dados do mirror.

## Detalhe e navegação

O header sticky e a área rolável são separados tanto no drawer de Link quanto no de Provider. Um Provider pode abrir um Link associado sem trocar de página. O Link oferece ações de Cockpit com os filtros suportados (Provider e UF) e de Rankings pelo ID CMDB do Provider. Rankings abre o detalhe do Provider em `/base/?view=providers&provider_id=<id>`; links individuais continuam usando `/base/?config_item_id=<id>`. Integrações do Mapa preservam os filtros e a navegação já existentes.

O CSV de Links mantém os filtros e o Data Scope da lista; nenhum dos CSVs inclui credenciais. Os models XLSX legados não participam do caminho operacional da Base.
