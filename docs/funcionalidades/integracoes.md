# Central de Integracoes

A pagina resume espelhos locais, ultima execucao, duracao, volume, status de freshness e saude do worker. CMDB mostra Links e Operadoras presentes; OTRS mostra tickets na fila, business-open, ultimo fast e ultimo full. Snapshot stale continua sendo mostrado.

Conectores CMDB ServiceUp e OTRS MySQL continuam disponiveis para configuracao, diagnostico e sincronizacao. OTRS e somente leitura. O worker e um processo separado: `.venv\Scripts\python.exe arion_geo\gerenciar.py integration_worker`; cadencias OTRS fast 1 min/full 30 min e CMDB 10 min. Lease persistente evita sobreposicao, com recuperacao de lock expirado.

Importacao XLSX esta desativada como operacao normal. Run e auditoria registram operacao e contagens sanitizadas, sem payload bruto ou segredo. Nao ha rota/modulo Chamados nesta fase.


A protecao de credenciais locais usa `WindowsDPAPISecretProtector` no Windows e permanece fora de respostas HTTP.
