# Dashboard

O Dashboard combina os Links atuais do mirror CMDB e os tickets presentes na fila exata `NOC - ATACADO`. As consultas usam o banco local; a página não chama ServiceUp nem o MySQL do OTRS. Links e tickets respeitam o Data Scope aplicado no backend.

## Período e snapshot

- `Tickets no período`, `Links reincidentes` e a evolução mensal usam `source_created_at`.
- Reincidência é um Link associado a pelo menos dois Tickets distintos no intervalo; a relação N:N não duplica o total de Tickets.
- `Chamados abertos agora` e `Situação atual dos chamados` são snapshots do espelho atual, independentes do período. Em atendimento e Pendentes compõem o total aberto.
- A situação mostra Em atendimento, Pendentes, Resolvidos, Encerrados, Cancelados e, somente quando houver, Não classificados.
- O gráfico compara tickets criados no mês com a quantidade de Links que tiveram dois ou mais tickets distintos naquele mês. Não representa histórico de backlog.

## Operadoras macro

O agrupamento VIVO, CLARO, ALGAR e OUTROS reutiliza a classificação histórica copiada uma única vez para `CMDBLinkMirror.legacy_operator_classification`. A migração associou os valores locais antigos a `CMDBLinkMirror.source_number`; não há leitura de XLSX nem do model legado em tempo de execução. Na base analisada em 23/10/2026, 3.418 dos 3.435 Links atuais tinham correspondência por número; 2.470 tinham classificação VIVO, CLARO ou ALGAR e os demais são apresentados como OUTROS.

Essa classificação foi originalmente derivada de correspondências textuais no nome/designação do Link. Portanto, o vínculo persistido é reproduzível e tem cobertura de associação alta, mas não confirma a operadora contratada como fonte oficial. A CMDB atual identifica o ISP/provedor local separadamente, e esse campo não é usado como operadora macro.

## Outros indicadores

- Total de Links: itens presentes no mirror CMDB.
- Estados atendidos e Top 10: UFs válidas distintas e distribuição de Links presentes.
- Freshness e atualização de dados continuam vinculadas aos mirrors e integrações existentes.
