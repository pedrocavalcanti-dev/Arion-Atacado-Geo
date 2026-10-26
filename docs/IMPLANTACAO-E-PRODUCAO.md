# Implantação e Produção

## Arquitetura V1

```text
Navegador HTTPS → Cloudflare → Cloudflare Tunnel → cloudflared
              → Waitress em 127.0.0.1:<ARION_WEB_PORT> → Django → MySQL local

Integration Worker → MySQL ARION local
                   → OTRS remoto somente leitura
                   → CMDB remota somente leitura
```

O repositório prepara o modo production e os processos Windows; ainda são manuais a máquina, domínio, conta Cloudflare, DNS, criação do Tunnel, credenciais e usuário de serviço. Não há proxy reverso adicional. O Worker é processo separado e nunca é iniciado por uma request.

## Modo production e servidor web

`ARION_ENV=production` exige `DEBUG=False`, `DJANGO_SECRET_KEY` forte e externa ao código, `DJANGO_ALLOWED_HOSTS` e `DJANGO_CSRF_TRUSTED_ORIGINS` explícitos. Produção aceita somente origens CSRF HTTPS exatas, MySQL em loopback e usuário MySQL próprio diferente de `root`. A aplicação encerra a inicialização se esses requisitos falharem.

O supervisor em `deploy/windows/run_process.py` inicia Waitress com bind fixo em `127.0.0.1` e porta de `ARION_WEB_PORT` no `.env` (padrão 8000). A request pública HTTPS chega pelo Tunnel; `X-Forwarded-Proto=https` é confiável porque o serviço WSGI só escuta loopback. Django ativa `SECURE_PROXY_SSL_HEADER` e `SECURE_SSL_REDIRECT`; valide o ciclo pelo Tunnel antes de liberar o hostname. Não execute `runserver` em produção.

Sessão e CSRF usam cookies `Secure`, `SameSite=Lax`; o cookie de sessão é `HttpOnly`. O cookie CSRF permanece legível pelo JavaScript para os POSTs AJAX same-origin. HSTS começa em 3600 segundos; `includeSubDomains` e `preload` ficam desativados. CSP está em `Report-Only` para permitir validação de Mapbox antes de enforcement. Respostas dinâmicas recebem `Cache-Control: private, no-store`; cache público deve ser limitado a estáticos.

## Build de frontend

Fontes legíveis ficam em `frontend_src/`, fora dos diretórios coletados pelo Django em production. `npm run build:production` produz bundles minificados, mangled e obfuscados em `arion_geo/static/arion_build/` e um manifest em `var/`. Não é criptografia. Source maps são desligados no build e ignorados pelo Git. Em development, o template tag `{% arion_js %}` resolve as fontes; em production, resolve apenas bundles registrados.

Use Node 24, conforme `package.json`, e o lockfile versionado:

```powershell
npm ci
npm audit
npm run build:production
```

Não publicar o `frontend_src` como static nem aplicar regras Cloudflare de cache amplo ao HTML.

## Preparação local Windows

Instale Python 3.12 e dependências de `requirements-prod.txt`; para o build, instale Node 24. Configure `.env` fora do Git a partir de `.env.example`, crie o MySQL local e restaure nele o dump operacional completo. Use a mesma conta Windows dedicada `ARION` para Web e Worker. A conta precisa ler `.env` e `var/database-config.json`, acessar `var/`, abrir credenciais DPAPI e executar os processos.

```powershell
deploy\windows\install-arion.ps1
deploy\windows\production-check.ps1
deploy\windows\install-tasks.ps1 -ServiceAccount '.\ARION'
deploy\windows\status-arion.ps1
```

`install-arion.ps1` executa `npm ci`/build quando Node está disponível, coleta estáticos e executa o production-check. Ele não sincroniza fontes remotas nem altera a conta Cloudflare. `-ApplyMigrations` exige confirmação explícita; migrations são executadas somente depois do restore completo e da conferência do banco alvo. As tarefas agendadas iniciam no boot, rodam ocultas, usam a `.venv` e reiniciam processos encerrados. O supervisor grava `var/logs/arion-web.log` e `arion-worker.log` com rotação; `status-arion.ps1` informa Web, Worker e Cloudflared sem mostrar segredos.

## Cloudflare Tunnel e proteção perimetral

`deploy/windows/cloudflare/config.example.yml` é apenas um modelo. O serviço Windows usa config e credentials-file em `C:\Windows\System32\config\systemprofile\.cloudflared`; o script de instalação copia o JSON local para essa pasta e restringe ACL para SYSTEM/Administrators. Não coloque token, `cert.pem`, JSON de credenciais ou config preenchida no repositório. A instalação do serviço exige Tunnel UUID, hostname, `cloudflared.exe` e JSON previamente obtidos pela equipe responsável; o script não cria Tunnel, DNS ou hostname.

O ingress encaminha somente para `http://127.0.0.1:<porta>` e encerra com `http_status:404`. O Tunnel é uma conexão outbound; mantenha inbound público fechado para 8000, 3306, 80 e 443. O MySQL deve escutar em loopback, sem acesso público. Nenhum Caddy, Nginx ou Apache é necessário nesta V1.

Na conta Cloudflare, configurar e revisar:

- DNS/hostname apontando para o Tunnel correto e health/conectividade do Tunnel;
- WAF e Managed Rules compatíveis com as rotas do ARION;
- rate limiting, managed challenge e proteção de bots em `/login/`, conforme recursos disponíveis no plano;
- Security Events e alertas de indisponibilidade;
- cache bypass para páginas dinâmicas, `/api/*`, `/ari/api/*`, `/base/api/*`, `/rankings/*`, `/chamados/*`, `/dashboard/*`, `/cockpit/*`, `/configuracoes/*` e `/admin/*`; cache somente de `/static/*`;
- restrição do token público Mapbox ao hostname de produção no painel Mapbox.

Cloudflare Access pode ser avaliado futuramente, mas não faz parte da V1 e não deve ser ativado por estes scripts.

## Worker e integrações

O comando de produção é executado pelo supervisor, não pelo Django web:

```powershell
.venv\Scripts\python.exe arion_geo\gerenciar.py integration_worker
```

Cadências permanecem OTRS FAST 2 min, OTRS FULL 30 min e CMDB FULL 10 min. Windows supervisiona o processo e `IntegrationLease` evita trabalho concorrente entre processos/instâncias. Não instale outro scheduler. A conexão OTRS precisa de grants somente leitura; CMDB usa operações Search/Get. Após restore e configuração de credenciais, execute FULL CMDB e FULL OTRS e verifique freshness, estados e lease antes da liberação.

## DPAPI e segredos

DPAPI usa o contexto do usuário Windows que protegeu o segredo. Um segredo protegido pelo usuário `ARION` pode não ser aberto por `SYSTEM`, outro usuário ou um serviço iniciado com outra identidade. Cadastre os segredos depois de definir a conta de serviço e sempre sob o mesmo usuário que executará Web e Worker. Não migre ciphertext DPAPI automaticamente entre usuários/máquinas; reconfigure segredos no novo host. O instalador das tarefas restringe ACL de `.env`, configuração local do banco, logs, runtime e mídia.

Nunca grave no log ou mostre em tela `SECRET_KEY`, senha, token, `DATABASE_URL`, Tunnel credentials, Authorization, Cookie ou secret de integração.

## MySQL e transferência para a máquina nova

O sistema atual já utiliza MySQL. A transferência é um dump e restore completos do MySQL atual para o MySQL local novo, preservando users, Groups/Permissions, Data Scope, preferências, tracking/notas/eventos, filas pessoais, auditoria, ARI, Saved Views, integrações e mirrors locais. FULL OTRS/CMDB não recompõe os dados próprios do ARION.

1. Planeje janela e consistência; pare Web/Worker de origem durante o dump final se for necessário congelar escritas locais.
2. Use `deploy/windows/backup-arion.ps1` na origem ou ferramenta equivalente para criar o dump completo com timestamp fora da pasta web. O script lê a conexão ativa do ARION/DPAPI, usa arquivo temporário de opções protegido por ACL, não coloca senha na linha de comando e remove esse arquivo ao terminar.
3. No host novo, crie o schema e um usuário próprio do ARION. Não use `root`; limite grants ao schema e às operações de leitura/escrita necessárias à aplicação, ao Worker e às migrations planejadas. Não exponha 3306 à rede pública.
4. Transfira o dump por canal protegido, restaure-o por procedimento manual e confirme contagens/tabelas críticas. O backup inclui dados locais e mirrors, não apenas snapshots sincronizáveis.
5. Configure `.env` e credenciais DPAPI no usuário `ARION`, execute migrations necessárias, `check`, testes e production-check; então execute FULL CMDB e OTRS.

Não use SQLite como caminho principal desta migração. Não restaure o banco durante esta auditoria.

## Backup e restore

`backup-arion.ps1` grava por padrão em `arion-backups` ao lado do projeto, fora do web root; `-BackupDirectory` muda o destino e `-RetentionDays` configura retenção (0 desativa a remoção automática). Restrinja a pasta, inclua cópia offline/externa conforme política da organização e agende o script sob a mesma conta Windows com DPAPI. Monitore o exit code, tamanho/idade do dump e faça ensaios de restore.

Restore é manual e destrutivo. Antes de restaurar: pare Web e Worker, crie e confirme um backup explícito do banco de destino, confira host/schema/arquivo e obtenha confirmação operacional explícita. Use credencial protegida e importe o dump completo. Depois valide migrations, integridade, permissions, Data Scope, `check` e acessos antes de iniciar os processos. Nenhum script deste repositório automatiza restore.

## Checklist antes de abrir

- `production-check.ps1`, `check --deploy`, `makemigrations --check --dry-run` e testes relevantes aprovados;
- `npm ci`, `npm audit` e build com resultado registrado; `collectstatic` sem sources ou `.map`;
- restore completo conferido, conta MySQL local não-root e grants mínimos;
- mesma conta Windows `ARION` para Web/Worker e credenciais DPAPI cadastradas nesse contexto;
- tarefas de Web/Worker ativas no boot, recovery e logs conferidos;
- serviço Cloudflared ativo no boot, config validada, ingress limitado a loopback e Tunnel saudável;
- domínio/CSRF/HTTPS, WAF, rate limit, cache bypass, eventos de segurança e Mapbox testados no hostname;
- smoke test de Login, Dashboard, Chamados, Cockpit, Mapa, Rankings, Base, Documentação e ARI;
- backup externo e procedimento de restore documentados e ensaiados.
