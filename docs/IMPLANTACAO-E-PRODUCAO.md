# Implantacao e producao

## Web e worker

O worker deve rodar como processo separado do servidor Django/Waitress; nao e iniciado no ciclo HTTP, middleware ou `AppConfig.ready()`. No Windows, execute sob a mesma conta de servico que pode abrir as credenciais DPAPI:

`.venv\Scripts\python.exe arion_geo\gerenciar.py integration_worker`

O comando aceita `--interval` (verificacao padrao a cada 5 s, maximo 60 s) e `--once` para avaliar um ciclo. CTRL+C encerra de forma limpa. Nao instala servico Windows automaticamente. Sem worker, a web continua lendo o snapshot local e a Central informa freshness stale/unavailable.

Cadencias: OTRS fast 2 min, full 30 min; CMDB full 10 min. Uma lease persistente por fonte protege tambem execucoes manuais; heartbeat a cada 20 s e expiracao apos 180 s permitem recuperacao apos processo morto. OTRS incremental usa `change_time`, safety window de 2 min e cursor atualizado somente apos apply local bem-sucedido. FAST consulta tickets novos/alterados e atualiza relacoes em lote apenas para os IDs afetados. FULL reconcilia a fila completa e tem prioridade sobre FAST. O primeiro OTRS sync e FULL quando ainda nao ha cursor.

## Pre-requisitos e operacao

Use `.venv\Scripts\python.exe arion_geo\gerenciar.py check` e `makemigrations --check`. Configure CMDB e OTRS em Central de Integracoes. O client OTRS deve usar usuario MySQL read-only. Execute primeiro full OTRS na instalacao inicial. Falha/indisponibilidade preserva o ultimo espelho valido; reconciliacao de ausencias so ocorre apos leitura completa.

O banco primario do Arion oferece suporte oficial a SQLite e MySQL. SQLite e apropriado para desenvolvimento, testes e instalacoes portateis; em producao, use MySQL. A conexao externa OTRS e independente e continua somente leitura. As leases do worker ficam no banco primario Arion. Nao configurar o processo web para executar scheduler embutido. `project_legacy` e dado de compatibilidade congelado, nao fonte oficial.

### Configuracao do banco Arion

A precedencia no inicio do processo e `DATABASE_URL`, arquivo local `var/database-config.json` na raiz do projeto e, por fim, SQLite padrao (`arion_geo/db.sqlite3`). `DATABASE_URL` tem precedencia e nao e sobrescrita pela Central. Sem essa variavel, a pagina **Banco Arion** em Central de Integracoes grava a configuracao fora do banco de dados, para que ela sobreviva a troca do proprio banco.

Na configuracao local, a senha MySQL e protegida com DPAPI para o usuario Windows que executa a aplicacao. Mover o arquivo para outro usuario/PC nao transfere a chave DPAPI; nesse caso, informe e salve novamente a senha no destino. Restrinja o acesso ao arquivo de configuracao e proteja tambem as variaveis de ambiente e backups.

MySQL Server 8.0.46/schema `arion_geo` foi validado anteriormente e os mirrors foram reconstruidos naquela execucao. Neste checkout, o bootstrap e o processo estao em SQLite; o candidato local `127.0.0.1:3306/arion_geo` passou no dry-run e tem 39 migrations aplicadas, mas ainda nao recebeu dados locais nem foi validado/ativado. Foi criado `arion-admin` no estado anterior; se a conta existir no SQLite, ajuste a senha pelo comando `changepassword`. A Central salva apenas um candidato. Siga o fluxo testar -> preparar -> copiar -> validar -> ativar; somente ativar muda o banco do proximo inicio. O rollback manual para SQLite esta disponivel na Central, no comando de gestao e no script independente.

Crie previamente o schema MySQL vazio com `utf8mb4` e configure o acesso como candidato na Central. O usuario deve ter privilegios para executar migrations Django. Depois, siga as fases controladas; nao use `migrate` diretamente para cortar SQLite -> MySQL, pois isso nao copia os dados locais:

```powershell
.venv\Scripts\python.exe arion_geo\gerenciar.py migrar_banco_arion --target=mysql --dry-run
.venv\Scripts\python.exe arion_geo\gerenciar.py migrar_banco_arion --target=mysql --prepare
.venv\Scripts\python.exe arion_geo\gerenciar.py migrar_banco_arion --target=mysql --copy-local-data
.venv\Scripts\python.exe arion_geo\gerenciar.py migrar_banco_arion --target=mysql --validate
.venv\Scripts\python.exe arion_geo\gerenciar.py migrar_banco_arion --target=mysql --activate
```

Somente `--activate` altera o banco usado no proximo inicio. Reinicie web e `integration_worker`; depois reconstrua CMDB e OTRS com FULL. Rollback explicito: `.venv\Scripts\python.exe arion_geo\gerenciar.py migrar_banco_arion --target=mysql --rollback`; se Django nao inicializar, use `.venv\Scripts\python.exe arion_geo\rollback_banco_arion.py`. Consulte `BANCO-DE-DADOS.md` para os models copiados e estados descartados.

A limpeza/retention de `IntegrationRun` detalhado ainda exige politica operacional antes de automatizar remocao. O modulo Chamados e escrita de tickets OTRS sao fases futuras; acoes futuras devem usar API/GenericInterface OTRS, nunca UPDATE MySQL direto.
