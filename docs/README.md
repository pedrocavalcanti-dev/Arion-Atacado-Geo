# Documentação — ARION ATACADO GEO

Índice oficial da documentação do projeto.

## Comece aqui

- [Projeto](PROJETO.md) — finalidade, módulos e princípios.
- [Estado Atual](ESTADO-ATUAL.md) — capacidades existentes hoje.
- [Arquitetura](ARQUITETURA.md) — desenho técnico e regras compartilhadas.
- [Fontes de Dados](FONTES-DE-DADOS.md) — origem REAL e DEMO e uso do escopo.

## Funcionalidades

- [Autenticação e Sessão](funcionalidades/autenticacao.md) — login e sessão Django.
- [ARI](funcionalidades/ari.md) — conversas, anexos e Preview.
- [Auditoria](funcionalidades/auditoria.md) — eventos funcionais e consulta.
- [Base de Links](funcionalidades/base.md) — espelho CMDB, busca e importação.
- [Cockpit](funcionalidades/cockpit.md) — análise, Saved Views e exports.
- [Configurações](funcionalidades/configuracoes.md) — central administrativa.
- [Dashboard](funcionalidades/dashboard.md) — visão executiva.
- [Integrações](funcionalidades/integracoes.md) — conectores e sincronização dos espelhos CMDB/OTRS.
- [Mapa Operacional](funcionalidades/mapa.md) — visualização por UF.
- [Ranking de Provedores](funcionalidades/ranking-provedores.md) — comparação REAL/DEMO.
- [Tratamento Global de Erros](funcionalidades/tratamento-global-erros.md) — handlers, API e logging.
- [Usuários, Grupos e Escopos](funcionalidades/usuarios-grupos-escopos.md) — RBAC e Data Scope.

## Segurança e operação

- [Banco de Dados](BANCO-DE-DADOS.md) — models, chaves e relações do espelho local.
- [Segurança](SEGURANCA.md) — controles atuais e limites de implantação.
- [Testes e QA](TESTES-E-QA.md) — comandos e cobertura existente.
- [Implantação e Produção](IMPLANTACAO-E-PRODUCAO.md) — configuração atual e dependências de ambiente.

## Interface

- [Diretrizes de Interface](DIRETRIZES-DE-INTERFACE.md) — temas, responsividade e padrões visuais.

## Desenvolvimento atual

- [Tarefa atual](tarefas/ATUAL.md) — estado da tarefa de desenvolvimento registrada.

## Banco e sincronização

O [modelo do banco](BANCO-DE-DADOS.md) documenta os espelhos CMDB e OTRS. Os
consumidores existentes ainda não foram migrados; Base XLSX, Dashboard, Cockpit,
Rankings, Mapa, ARI e Chamados continuam usando as fontes anteriores.

## Ordem recomendada de leitura

1. [Projeto](PROJETO.md)
2. [Estado Atual](ESTADO-ATUAL.md)
3. [Arquitetura](ARQUITETURA.md)
4. [Fontes de Dados](FONTES-DE-DADOS.md)
5. [Banco de Dados](BANCO-DE-DADOS.md)
6. [Segurança](SEGURANCA.md)
7. [Funcionalidades](funcionalidades/)
8. [Testes e QA](TESTES-E-QA.md)
9. [Implantação e Produção](IMPLANTACAO-E-PRODUCAO.md)
