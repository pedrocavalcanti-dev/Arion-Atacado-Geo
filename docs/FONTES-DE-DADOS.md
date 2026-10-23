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

`em atendimento` -> `OPEN`; `Pendente` -> `PENDING`; `resolvido` -> `RESOLVED`; `closed successful` e `Encerrado com viabilidade` -> `CLOSED`; `cancelado` -> `CANCELED`; estado nao reconhecido -> `UNKNOWN`. Apenas `OPEN` e `PENDING` sao `is_business_open=True`.

KPIs globais contam tickets distintos. Ticket associado a multiplos Links conta uma vez no total geral e em cada Link associado. Para Data Scope `CUSTOM`, ticket sem relacao confirmavel com Link permitido nao e exposto. SLA e apresentado por nome e nao se calcula cumprimento sem regra de negocio confirmada. Nao ha serie historica de estados: backlog e abertos sao snapshot atual; periodos de volume usam `source_created_at`.

## Sincronizacao e freshness

Execute o worker dedicado com `.venv\Scripts\python.exe arion_geo\gerenciar.py integration_worker`. OTRS incremental roda a cada 1 minuto, reconciliacao completa a cada 30 minutos e CMDB completo a cada 10 minutos. A primeira execucao OTRS e full. Um lease persistente por fonte impede concorrencia entre processos, com heartbeat e expiracao de 180 segundos. O incremental usa `ticket.change_time` e sobreposicao de 2 minutos; cursor so avanca apos apply local bem-sucedido. Relacoes dos tickets afetados sao consultadas em lote. A interface de Integracoes mostra snapshots e freshness local; `stale` nao apaga dados nem zera indicadores.

Comandos manuais: `sincronizar_cmdb --apply`, `sincronizar_otrs --queue "NOC - ATACADO" --full --apply` e `sincronizar_otrs --queue "NOC - ATACADO" --fast --apply`. Eles usam os mesmos leases. Full sync so reconcilia ausencias depois de fetch completo.

## Data Scope

`ALL` permite o universo funcional inteiro. `CUSTOM` cruza Operadora permitida E Projeto permitido; o Projeto usa apenas o valor transitorio congelado `legacy_project`. Link sem Projeto nao ganha acesso por ausencia de dado. Usuario sem grupo/configuracao e listas vazias sao restritivos; superuser mantem bypass global. O escopo e aplicado na query layer antes de filtros, agregacoes, paginacao, APIs e exportacoes.

## Dados protegidos e limites

Campos de senha CMDB (`SenhaPPOE`, `SenhaPortalOperadora`) nao sao persistidos em mirrors. O conector OTRS permanece read-only e nao copia senha, `users.pw`, tokens, artigos ou corpos de mensagens. Nao existe modulo `/chamados/` nem escrita no OTRS nesta fase.

A ARI segue como Preview isolada com artefatos demonstrativos explicitamente identificados; nao alimenta os modulos operacionais.

## Estudos

Conclusoes e inventarios de schema ficam em `docs/estudos/`. Contagens registradas nos estudos sao fotografias datadas, nao constantes do codigo.


## Snapshot validado em 23/10/2026

Apos full CMDB, full OTRS e fast OTRS aplicados: 3.435 Links CMDB presentes e 1.329 Operadoras presentes. ISP: 3.316 resolvidos por ConfigItemID, 17 por nome exato, 99 nao resolvidos e 3 vazios. Full CMDB levou 54,5 s.

A fila `NOC - ATACADO` resolveu para ID 107 e contem 11.963 tickets: `OPEN=18`, `PENDING=3`, `RESOLVED=21`, `CLOSED=10.936`, `CANCELED=985`, `UNKNOWN=0`; business-open=21. Full OTRS levou 179,3 s. O fast seguinte levou 1,0 s e nao encontrou alteracoes, mantendo snapshot e cursor, comprovando idempotencia.

Foram espelhadas 7.497 relacoes Ticket-ConfigItem: 7.493 tickets com CI, 4.470 sem CI, 7.489 tickets com um CI, 4 com multiplos CIs, 2.009 ConfigItems unicos e 1.444 ConfigItems ligados a mais de um ticket. As 7.497 relacoes resolveram para Link local; nenhuma ficou sem Link.
## Semantica dos espelhos validada em 23/10/2026

`CMDBLinkMirror.isp_raw` corresponde ao `ConfigItemID` de itens da classe CMDB chamada `Operadoras` em 3.316 links; outros 17 resolveram por nome exato. A relacao resolvida representa o nome de Provedor/ISP do Link com forte evidencia. O ID bruto nunca deve ser apresentado como nome.

Nao foi encontrada fonte oficial confiavel para Projeto nem para Operadora contratada. `legacy_project` e um campo historico copiado do XLSX e nao e atualizado pela sincronizacao. `DesignacaoOperadora`, numero do contrato e SLA nao sao prova da operadora contratada. A definicao e a contagem dos campos candidatos estao em `docs/estudos/MAPEAMENTO-NEGOCIO-CMDB-OTRS.md`.

`TicketQueryService.noc_tickets()` e a base operacional compartilhada: nome exato `NOC - ATACADO` e presenca atual na fila. Volume por periodo usa `source_created_at`; backlog e snapshot atual OPEN + PENDING e nao herda o filtro de criacao. RESOLVED, CLOSED e CANCELED ficam fora do backlog.
