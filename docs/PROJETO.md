# Projeto — ARION OPS

> **Identidade visual:** Produto/interface **ARION OPS**. Empresa: **ARION**. Operação atendida: **NOC ATACADO**. O nome interno do projeto e repositório permanece ARION ATACADO GEO.

## Objetivo e público

O ARION OPS é uma plataforma Django de inteligência operacional. Reúne a base de links da CMDB, os chamados sincronizados do OTRS e o acompanhamento local da equipe. Dashboard, Cockpit, Mapa e Rankings reutilizam espelhos locais para cruzar chamado, Link, Provider/ISP, Cliente, Projeto e UF conforme as limitações das fontes disponíveis.

O sistema reduz a fragmentação entre consultas e facilita a leitura consolidada de fila, impacto, recorrência e distribuição geográfica. É uma ferramenta de exploração operacional diária; não substitui OTRS/CMDB como registro técnico nem BI/relatórios formais.

Usuários reais: analistas NOC, gestores, administradores de sistema e usuários de consulta/auditoria. O acesso deriva de Django Groups e Permissions; Data Scope restringe linhas operacionais no backend. Não há role separada chamada “apresentação”.

## Identidade visual e login

A interface do produto usa a marca **ARION OPS**; ARION identifica a empresa e NOC ATACADO, a operação atendida. O login institucional combina branding, formulário Django e carrossel de três artes. Avisos de nova versão são reservados às páginas autenticadas.

## Desenvolvimento

ARION OPS foi concebido e desenvolvido por Pedro Cavalcanti para apoio às operações do NOC Atacado da ARION. Produto: ARION OPS; operação: NOC Atacado; empresa: ARION Serviços de Telecomunicações. A página autenticada **Sobre o ARION OPS** apresenta este crédito e a versão atual do catálogo.

## Fontes oficiais e papel do banco local

OTRS é o registro oficial dos chamados e CMDB é a fonte oficial dos itens de configuração. O ARION não grava alterações nesses sistemas: OTRS é acessado em MySQL somente leitura e CMDB por operações de leitura de ConfigItems. O banco ARION contém mirrors sincronizados, preferências e dados próprios da aplicação, além de camadas analíticas.

Status ARION, responsável, prioridade interna, notas e eventos criados em Chamados pertencem ao ARION; não alteram o ticket OTRS. A freshness depende do `integration_worker`; as telas usam a última cópia local disponível.

## Módulos e limites

| Área | Capacidade | Limite |
|---|---|---|
| Dashboard | Links, tickets e séries de período. | Distingue estado atual de coortes por data de criação. |
| Chamados | Fila NOC, filtros e acompanhamento interno. | Não altera ticket, artigo ou nota no OTRS. |
| Cockpit | Analytics, views salvas e exports. | Consulta mirrors locais e respeita Data Scope. |
| Mapa e Rankings | Agregações geográficas e análise de Provider/ISP. | Não são relatório oficial de SLA nem prova de causalidade. |
| Base | Links e Providers/ISP do mirror CMDB. | Importação XLSX antiga não é ingestão operacional normal. |
| ARI | Conversas, anexos e artifacts em Preview. | Não anunciar integração LLM como disponível. |
| Administração | Conta, grupos, escopos, integrações e auditoria. | Operações exigem permissions backend. |

## Princípios

- A fonte oficial continua sendo OTRS/CMDB; o mirror é projeção local reconstruível.
- Views operacionais não consultam uma fonte remota em cada request.
- Data Scope é aplicado antes de filtros, agregações, paginação e exportação.
- Cliente/Projeto derivados do nome CMDB mantêm origem e confiança explícitas.
- Não apresentar métrica não suportada como SLA ou verdade oficial.
- Estudos e contagens pontuais ficam em `docs/estudos/`, fora da referência normativa.

Leia [Estado Atual](ESTADO-ATUAL.md), [Arquitetura](ARQUITETURA.md), [Fontes de Dados](FONTES-DE-DADOS.md), [Banco](BANCO-DE-DADOS.md), [Chamados](funcionalidades/chamados.md) e [Implantação](IMPLANTACAO-E-PRODUCAO.md). A Central web usa estas páginas versionadas como fonte.
