# Fontes de dados e escopo

## Fontes operacionais

OTRS / CMDB permanece como fonte oficial. As paginas operacionais consultam somente o banco Arion, que mantem espelhos locais atualizados por processos separados.

- Links e operadoras: `CMDBLinkMirror` e `CMDBOperatorMirror`, via ServiceUp `ConfigItemSearch` / `ConfigItemGet`.
- Tickets atuais da fila `NOC - ATACADO`: `OTRSTicket`, sincronizados por cliente MySQL OTRS somente de leitura.
- Relacao: `OTRSTicketConfigItem` associa Ticket a `ConfigItemID` e, quando resolvida, ao Link local.
- `CMDBLinkMirror.is_present_in_source=True` e `OTRSTicket.is_present_in_queue=True` definem o universo operacional atual.

XLSX esta descontinuado como fonte operacional. Os modelos, migrations e importador antigo permanecem no repositorio para compatibilidade/rollback, mas a UI normal nao permite importacao e Base, Dashboard, Cockpit, Mapa e Rankings nao consultam tabelas XLSX. `project_legacy` e um valor congelado copiado anteriormente para compatibilidade de filtro e autorizacao; `project_source=LEGACY_XLSX` documenta sua origem. Nao e um campo oficial de Projeto CMDB e nao e atualizado por sincronizacao.

Nenhum request dessas paginas abre conexao com CMDB ou OTRS. Falhas externas mantem o ultimo espelho local valido.

## Estados de negocio e metricas

`em atendimento` -> `OPEN`; `Pendente` -> `PENDING`; `agendado` -> `SCHEDULED`; `resolvido` -> `RESOLVED`; `closed successful` e `Encerrado com viabilidade` -> `CLOSED`; `cancelado` -> `CANCELED`; estado nao reconhecido -> `UNKNOWN`. `OPEN`, `PENDING` e `SCHEDULED` sao `is_business_open=True`; os demais estados nao compoem backlog.

KPIs globais contam tickets distintos. Ticket associado a multiplos Links conta uma vez no total geral e em cada Link associado. Para Data Scope `CUSTOM`, ticket sem relacao confirmavel com Link permitido nao e exposto. SLA e apresentado por nome e nao se calcula cumprimento sem regra de negocio confirmada. Nao ha serie historica de estados: backlog e abertos sao snapshot atual; periodos de volume usam `source_created_at`.

## Sincronizacao e freshness

Execute o worker dedicado com `.venv\Scripts\python.exe arion_geo\gerenciar.py integration_worker`. OTRS incremental roda a cada 2 minutos, reconciliacao completa a cada 30 minutos e CMDB completo a cada 10 minutos. A primeira execucao OTRS e full. Um lease persistente por fonte impede concorrencia entre processos, com heartbeat e expiracao de 180 segundos. O incremental usa `ticket.change_time` e sobreposicao de 2 minutos; cursor so avanca apos apply local bem-sucedido. Relacoes dos tickets afetados sao consultadas em lote. A interface de Integracoes mostra snapshots e freshness local; `stale` nao apaga dados nem zera indicadores.

Comandos manuais: `sincronizar_cmdb --apply`, `sincronizar_otrs --queue "NOC - ATACADO" --full --apply` e `sincronizar_otrs --queue "NOC - ATACADO" --fast --apply`. Eles usam os mesmos leases. Full sync so reconcilia ausencias depois de fetch completo.

## Data Scope

`ALL` permite o universo funcional inteiro. `CUSTOM` cruza Operadora permitida E Projeto permitido; o Projeto usa apenas o valor transitorio congelado `legacy_project`. Link sem Projeto nao ganha acesso por ausencia de dado. Usuario sem grupo/configuracao e listas vazias sao restritivos; superuser mantem bypass global. O escopo e aplicado na query layer antes de filtros, agregacoes, paginacao, APIs e exportacoes.

## Dados protegidos e limites

Campos de senha CMDB (`SenhaPPOE`, `SenhaPortalOperadora`) nao sao persistidos em mirrors. O conector OTRS permanece read-only e nao copia senha, `users.pw`, tokens, artigos ou corpos de mensagens. Nao existe modulo `/chamados/` nem escrita no OTRS nesta fase.

A ARI segue como Preview isolada com artefatos demonstrativos explicitamente identificados; nao alimenta os modulos operacionais.

## Estudos

Conclusoes e inventarios de schema ficam em `docs/estudos/`. Contagens registradas nos estudos sao fotografias datadas, nao constantes do codigo.


## Snapshot local consultado em 24/10/2026

O mirror CMDB contém 3.437 links atuais e 1.330 operadoras presentes. O FULL OTRS consultado em 24/10/2026 encontrou a fila `NOC - ATACADO` (ID 107), 11.973 tickets e 7.505 relações Ticket-ConfigItem; todas resolveram para Link local. Os estados espelhados foram `OPEN=7`, `PENDING=5`, `SCHEDULED=7`, `RESOLVED=0`, `CLOSED=10.968`, `CANCELED=986` e `UNKNOWN=0`; backlog atual=19. O FULL levou 134,9 s e usou 104 SELECTs; atualizou 1.849 tickets e manteve 10.124 inalterados.

Há 7.501 tickets com CI, 4.472 sem CI, 7.497 com exatamente um CI e 4 com múltiplos CIs. Há 2.011 ConfigItemIDs distintos; 1.445 deles estão relacionados a mais de um ticket.

O estudo read-only confirmou o Dynamic Field Ticket `RvalidacaoProcedenteImprocedente`, label `Validação`, tipo `Dropdown`, na tabela `dynamic_field`; seus valores são lidos de `dynamic_field_value`. Entre os 11.973 tickets atuais, 1.848 (15,43%) têm classificação: 1.505 `Procedente` e 343 `Improcedente`. No período de 01/10 a 24/10/2026, 534 tickets válidos da fila tinham classificação: 429 Procedente, 84 Improcedente e 21 sem classificação. Entre 517 tickets distintos relacionados aos Providers, os números foram 421, 77 e 19, respectivamente. Códigos de fechamento como `SemIntervencaoTecnica` aparecem tanto com Procedente quanto com Improcedente; o campo não comprova culpa do Provider nem altera o Índice ARION V1.

## Semantica dos espelhos validada em 23/10/2026

`CMDBLinkMirror.isp_raw` corresponde ao `ConfigItemID` de itens da classe CMDB chamada `Operadoras` em 3.316 links; outros 17 resolveram por nome exato. A relacao resolvida representa o nome de Provedor/ISP do Link com forte evidencia. O ID bruto nunca deve ser apresentado como nome.

Nao foi encontrada fonte oficial confiavel para Projeto nem para Operadora contratada. `legacy_project` e um campo historico copiado do XLSX e nao e atualizado pela sincronizacao. `DesignacaoOperadora`, numero do contrato e SLA nao sao prova da operadora contratada. A definicao e a contagem dos campos candidatos estao em `docs/estudos/MAPEAMENTO-NEGOCIO-CMDB-OTRS.md`.

`TicketQueryService.noc_tickets()` e a base operacional compartilhada: nome exato `NOC - ATACADO` e presenca atual na fila. Volume por periodo usa `source_created_at`; backlog e snapshot atual OPEN + PENDING + SCHEDULED e nao herda o filtro de criacao. SCHEDULED e categoria distinta de PENDING. RESOLVED, CLOSED, CANCELED e UNKNOWN ficam fora do backlog.
