# Seguranca

## Acesso a dados

RBAC usa Django Groups/Permissions e Data Scope controla linhas. O escopo e imposto no backend na query layer antes de filtros, agregacoes, paginacao, detalhes, API e export. CUSTOM exige Operadora permitida E Projeto congelado permitido. Link sem Projeto nao recebe acesso automaticamente. Ticket sem associacao a Link autorizado nao aparece para usuario CUSTOM. Superuser mantem bypass; ausencia de grupo/escopo e restritiva.

## Integracoes e segredos

CMDB ServiceUp usa endpoints de leitura Search/Get. OTRS conecta por client MySQL separado, somente leitura; nenhum request analitico consulta origem. Senhas PPOE/portal nao sao persistidas em mirrors. Segredo de conexao e protegido por DPAPI no sistema Windows existente e nunca enviado a interface, logs ou auditoria. O espelho nao copia `users.pw`, tokens, artigos ou corpos de mensagens.

A importacao XLSX esta desativada na interface normal; rotas legadas nao aplicam importacao. Tabelas antigas permanecem para rollback sem consumo operacional.

AuditService registra a operacao de sincronizacao sem gerar evento por ticket. O worker usa lease no banco com token, heartbeat e expiracao para impedir concorrencia e recuperar encerramento abrupto.
