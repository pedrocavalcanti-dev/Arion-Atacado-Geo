# Documentação oficial — ARION OPS

Esta pasta é a fonte Markdown da Central web em `/configuracoes/documentacao/`. Produto/interface: **ARION OPS**; empresa: **ARION**; operação atendida: **NOC ATACADO**. O nome interno do projeto e repositório permanece ARION ATACADO GEO. OTRS e CMDB permanecem fontes oficiais; o banco ARION contém mirrors e dados próprios.

## Desenvolvimento

ARION OPS foi concebido e desenvolvido por Pedro Cavalcanti para apoio às operações do NOC Atacado da ARION. A versão interna atual registrada no catálogo de releases é **1.2.0**; o mesmo catálogo alimenta `/api/version/`, a página de atualizações e a revisão do cache PWA.

## Identidade e atualizações

A identidade visual atual do produto é **ARION OPS**. O login institucional não exibe avisos PWA. Depois da autenticação, avisos de versão acompanham a navegação; o botão Depois registra a versão dispensada e mantém o indicador global acessível. Consulte [Estado Atual](ESTADO-ATUAL.md), [Autenticação e Sessão](funcionalidades/autenticacao.md) e [Arquitetura](ARQUITETURA.md).

## Começar

- [Projeto](PROJETO.md)
- [Estado Atual](ESTADO-ATUAL.md)
- [Arquitetura](ARQUITETURA.md)
- [Fontes de Dados](FONTES-DE-DADOS.md)

## Funcionalidades

- [Autenticação e Sessão](funcionalidades/autenticacao.md)
- [Dashboard](funcionalidades/dashboard.md)
- [Chamados](funcionalidades/chamados.md)
- [Cockpit](funcionalidades/cockpit.md)
- [Mapa Operacional](funcionalidades/mapa.md)
- [Ranking de Provedores](funcionalidades/rankings.md)
- [Central de Relatórios](funcionalidades/relatorios.md)
- [Base de Links](funcionalidades/base.md)
- [ARI](funcionalidades/ari.md)

## Dados e Integrações

- [Banco de Dados e Modelos](BANCO-DE-DADOS.md)
- [OTRS](OTRS.md)
- [CMDB](CMDB.md)
- [Worker e Sincronização](WORKER-E-SINCRONIZACAO.md)
- [Dicionário de Dados](DICIONARIO-DE-DADOS.md)

## Administração

- [Configurações](funcionalidades/configuracoes.md)
- [Integrações](funcionalidades/integracoes.md)
- [Usuários, Grupos e Escopos](funcionalidades/usuarios-grupos-escopos.md)
- [Auditoria](funcionalidades/auditoria.md)
- [Tratamento Global de Erros](funcionalidades/tratamento-global-erros.md)

## Segurança e operação

- [Segurança](SEGURANCA.md)
- [Testes e QA](TESTES-E-QA.md)
- [Implantação e Produção](IMPLANTACAO-E-PRODUCAO.md)

## Padrões

- [Diretrizes de Interface](DIRETRIZES-DE-INTERFACE.md)

## Estudos e tarefas

`estudos/` contém snapshots e pesquisas datadas; não substituem contratos da referência normativa. `tarefas/ATUAL.md` é uma nota histórica de tarefa concluída, não estado de capacidade atual.

O [Roadmap](ROADMAP.md) separa os itens concluídos na 1.2.0 das melhorias futuras, sem substituir a documentação funcional vigente.

## Ordem sugerida

1. Projeto e Estado Atual.
2. Arquitetura e Fontes de Dados.
3. Banco, OTRS, CMDB e Worker.
4. Chamados, Cockpit, Mapa e Rankings.
5. Data Scope, Segurança, Testes e Implantação.
