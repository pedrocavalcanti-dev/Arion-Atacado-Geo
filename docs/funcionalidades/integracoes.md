# Central de Integracoes

A pagina resume espelhos locais, ultima execucao, duracao, volume, status de freshness e saude do worker. CMDB mostra Links e Operadoras presentes; OTRS mostra tickets na fila, business-open, ultimo fast e ultimo full. Snapshot stale continua sendo mostrado.

O espelho OTRS classifica estados explicitamente: OPEN, PENDING e SCHEDULED (Agendado) compoem o backlog atual, preservando Agendado como status separado. FULL reclassifica os tickets ja espelhados; FAST mantem a atualizacao incremental.

Conectores CMDB ServiceUp e OTRS MySQL continuam disponiveis para configuracao, diagnostico e sincronizacao. OTRS e somente leitura. O worker e um processo separado: `.venv\Scripts\python.exe arion_geo\gerenciar.py integration_worker`; cadencias OTRS fast 2 min/full 30 min e CMDB 10 min. FAST consulta tickets novos/alterados por `ticket.change_time` com safety window de 2 min; atualiza somente tickets afetados, inclusive saidas da fila, e suas relacoes em lote. FULL reconcilia a fila completa. CMDB atualiza snapshot completo. Lease persistente evita sobreposicao, com heartbeat de 20 s e expiracao em 180 s.

Importacao XLSX esta desativada como operacao normal. Run e auditoria registram operacao e contagens sanitizadas, sem payload bruto ou segredo. Nao ha rota/modulo Chamados nesta fase.


A protecao de credenciais locais usa `WindowsDPAPISecretProtector` no Windows e permanece fora de respostas HTTP.

## Dynamic Fields e data terminal do OTRS

O FULL reconcilia e o FAST atualiza em lote somente `CodigoFechamento` (`dynamic_field_value.value_text`) e `ticketResolvido` (`value_date`) para os tickets selecionados por `ticket.change_time`. `OTRSTicket` espelha esses valores em `closing_code_raw` e `resolved_at`; `terminal_state_at` e `canceled_at` derivam do último `ticket_history` de tipo `StateUpdate` que corresponde ao estado atual. Todas as consultas remotas usam SELECT, sem histórico consultado em requests. A cadência do worker permanece FAST OTRS 2 min, FULL 30 min e CMDB 10 min.
