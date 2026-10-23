# Testes e QA

## Ambiente e comandos

O projeto usa Django TestCase e cliente de testes, com testes por app em `arion_geo/aplicativos/`. Na raiz, use o interpretador da `.venv`:

```powershell
.venv\Scripts\python.exe arion_geo\gerenciar.py check
.venv\Scripts\python.exe arion_geo\gerenciar.py makemigrations --check
.venv\Scripts\python.exe arion_geo\gerenciar.py test
```

Para executar uma suíte específica, informe o app ou caminho de teste, por exemplo `aplicativos.ari` ou `aplicativos.configuracoes.test_errors`. Testes criam banco isolado; não exigem alterar dados do banco de desenvolvimento.

## Cobertura existente

- `aplicativos.autenticacao.tests`: autenticação, contas ativas/inativas e fluxo de sessão.
- `aplicativos.configuracoes.tests` e `test_errors.py`: permissões, preferências, usuários/grupos/escopos, handlers HTTP, CSRF, JSON e proteção de respostas 500.
- `aplicativos.auditoria.tests`: sanitização de metadata, autenticação, mudanças administrativas e exportação.
- `aplicativos.ari.tests`: conversas, propriedade, anexos, limites/validação e artifacts.
- `aplicativos.base_links.tests`: importação XLSX, normalização, classificação, escopo, busca, filtros e paginação.
- `aplicativos.painel.tests`: Dashboard/Cockpit, fontes REAL/DEMO, consultas, escopo, Saved Views e exportação.
- `aplicativos.mapa.tests`: acesso, agregações e escopo do endpoint geográfico.
- `aplicativos.rankings.tests`: filtros, ordenação, paginação, agregação e Data Scope.

## Verificações antes de entrega

Execute `check`, `makemigrations --check` quando aplicável e testes relevantes; tarefas de documentação ou CSS não exigem inventar testes. Mudanças em arquivos globais de template/autorização pedem smoke test autenticado das rotas afetadas. `git diff --check` verifica whitespace do diff. Testes de browser e cobertura percentual não estão configurados como pipeline neste repositório.
