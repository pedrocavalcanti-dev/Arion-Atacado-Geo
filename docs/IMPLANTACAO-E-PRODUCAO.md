# Implantacao e producao

## Web e worker

O worker deve rodar como processo separado do servidor Django/Waitress; nao e iniciado no ciclo HTTP, middleware ou `AppConfig.ready()`. No Windows, execute sob a mesma conta de servico que pode abrir as credenciais DPAPI:

`.venv\Scripts\python.exe arion_geo\gerenciar.py integration_worker`

O comando aceita `--interval` (verificacao padrao a cada 5 s, maximo 60 s) e `--once` para avaliar um ciclo. CTRL+C encerra de forma limpa. Nao instala servico Windows automaticamente. Sem worker, a web continua lendo o snapshot local e a Central informa freshness stale/unavailable.

Cadencias: OTRS fast 1 min, full 30 min; CMDB full 10 min. Uma lease persistente por fonte protege tambem execucoes manuais; heartbeat a cada 20 s e expiracao apos 180 s permitem recuperacao apos processo morto. OTRS incremental usa `change_time`, sobreposicao de 2 min e cursor atualizado somente apos apply local bem-sucedido.

## Pre-requisitos e operacao

Use `.venv\Scripts\python.exe arion_geo\gerenciar.py check` e `makemigrations --check`. Configure CMDB e OTRS em Central de Integracoes. O client OTRS deve usar usuario MySQL read-only. Execute primeiro full OTRS na instalacao inicial. Falha/indisponibilidade preserva o ultimo espelho valido; reconciliacao de ausencias so ocorre apos leitura completa.

SQLite e usado em desenvolvimento e MariaDB em producao; as leases sao armazenadas no banco Arion. Nao configurar o processo web para executar scheduler embutido. `project_legacy` e dado de compatibilidade congelado, nao fonte oficial.

A limpeza/retention de `IntegrationRun` detalhado ainda exige politica operacional antes de automatizar remocao. O modulo Chamados e escrita de tickets OTRS sao fases futuras; acoes futuras devem usar API/GenericInterface OTRS, nunca UPDATE MySQL direto.
