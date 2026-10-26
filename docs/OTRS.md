# OTRS

## Fonte oficial e limite de escrita

OTRS é a fonte oficial dos tickets, estados, relações com ConfigItems e Dynamic Fields. O ARION mantém um espelho local para consulta e análise; Chamados, Dashboard, Cockpit, Mapa e Rankings não escrevem no OTRS e não consultam o servidor remoto durante uma request web.

A integração conecta ao MySQL do OTRS com uma conta dedicada de leitura. O client `OTRSReadOnlyClient` inicia a sessão MySQL em modo somente leitura e limita as consultas de inspeção a `SELECT` e metadados. A conta remota também deve receber grants somente de leitura, limitados ao schema necessário.

## Fila e sincronização

O worker sincroniza a fila exata `NOC - ATACADO`. OTRS FAST busca alterações recentes a cada 2 minutos; OTRS FULL reconcilia a fila a cada 30 minutos. `IntegrationLease` evita execução concorrente. Falha ou timeout preserva o último snapshot local e não deve ser interpretado como fila vazia.

Os tickets locais preservam a identidade externa do OTRS. `ticket.id` é a chave técnica externa e `ticket.tn` é o número apresentado ao usuário; o ARION não os trata como a mesma coluna. Relações Ticket–ConfigItem são espelhadas separadamente para que um ticket associado a vários itens continue navegável. Saída da fila não significa, por si só, que o ticket foi fechado.

O estado técnico recebido do OTRS é mantido no mirror e convertido pelo catálogo de estados usado pelo produto. Estado desconhecido não é inferido como aberto ou fechado. O campo dinâmico `CodigoFechamento` é preservado em `closing_code_raw`; `FalhaMassiva`, `Falha Massiva` e `Defeito Massivo` são aliases conhecidos da mesma categoria exibida. A canonicalização não apaga o valor original.

## Inspeção segura do schema

A inspeção administrativa de schema usa metadados de `information_schema`, valida database e tabela descobertos e limita a paginação de amostras. Consultas fornecidas ao estudo são restritas a um único `SELECT`; comandos de escrita, efeitos colaterais e leitura de conteúdo sensível são recusados. A amostra não permite explorar tabelas de artigos ou usuários de clientes, e colunas relacionadas a senha, token, sessão, autenticação, artigo, corpo ou nota interna são mascaradas.

O painel não deve expor senha, ciphertext DPAPI, `DATABASE_URL`, artigos, anexos ou corpo de mensagens. A credencial de OTRS é protegida localmente; DPAPI depende da conta Windows que a cadastrou. Depois de restaurar o banco em outra máquina, recadastre a credencial sob a mesma identidade de serviço usada pelo Worker.

## Operação

Configure host, schema, usuário read-only e segredo na Central de Integrações. Testes de conexão e exploração de schema são ações administrativas auditadas. Acompanhe a última execução FAST/FULL, cursor, lease, quantidade de tickets e estado do mirror em conjunto; uma tentativa malsucedida recente não substitui a última sincronização bem-sucedida.

O procedimento de operação e recuperação está em [Worker e Sincronização](WORKER-E-SINCRONIZACAO.md). Os campos e regras de identidade estão em [Dicionário de Dados](DICIONARIO-DE-DADOS.md), e a relação entre OTRS e os demais mirrors está em [Fontes de Dados](FONTES-DE-DADOS.md).
