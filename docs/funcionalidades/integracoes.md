# Central de Integrações

## Papel

A Central administra configuração dos conectores CMDB/OTRS e mostra saúde/freshness dos mirrors: última execução, tipo, duração, resultado e contagens. Não é cliente de consulta remota por request; sincronização roda no worker separado.

## Conectores e estado

- **CMDB ServiceUp:** GenericInterface Search/Get para classes `Links de internet` e `Operadoras`, destino local `CMDBLinkMirror` e `CMDBOperatorMirror`.
- **OTRS MySQL:** conexão read-only à fila exata `NOC - ATACADO`, estados, relações e Dynamic Fields selecionados; destino `OTRSTicket`, `OTRSTicketConfigItem` e `OTRSStateMapping`.

`Integration` guarda configuração protegida/status. `IntegrationRun` guarda tentativas sanitizadas. `IntegrationSyncState` persiste cursor, sucesso/último FULL e `IntegrationLease` coordena processos. Segredo aparece mascarado, nunca em response/API.

Cadências: OTRS FAST 2 min; OTRS FULL 30 min; CMDB FULL 10 min; retry 2 min. Ver [Worker](../WORKER-E-SINCRONIZACAO.md), [OTRS](../OTRS.md) e [CMDB](../CMDB.md).

## Diagnóstico

Leia resultado e último sucesso em conjunto: attempt FAILED recente não torna mirror fresco. Confira configuração/conectividade, último FAST/FULL, cursor e lease. OTRS depende da resolução do nome exato da fila; CMDB precisa resposta completa Search/Get. FULL valida conjunto antes de marcar ausências; falha conserva o último snapshot.

Segredos locais DPAPI dependem do usuário Windows de execução. Em outra conta ou máquina, cadastre de novo sem copiar credencial em ticket de suporte.

## Limites

Chamados não atualiza OTRS e Base não edita CMDB. Importador XLSX antigo não é uma integração oficial ativa. Runs não devem armazenar payload de ticket/credenciais. Permission de integração não substitui Data Scope dos dados operacionais.
