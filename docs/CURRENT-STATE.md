# Estado atual do projeto

Atualizado em: 22/10/2026

Este arquivo descreve somente o estado atual do ARION ATACADO GEO.

Para arquitetura e regras gerais, consultar:

- ../AGENTS.md
- PROJECT.md
- ARCHITECTURE.md
- DATA-SOURCES.md
- UI-GUIDELINES.md

---

# Navegação atual

A aplicação possui:

- Início
- Dashboard
- Cockpit
- Mapa
- Rankings
- Base
- ARI I.A

O menu deve permanecer simples.

---

# Fonte oficial

OTRS / CMDB é a fonte oficial dos dados operacionais.

O ARION ATACADO GEO não é uma segunda fonte de verdade.

O banco local serve como:

- espelho;
- cache;
- camada analítica;
- pesquisa;
- agregação;
- visualização.

---

# Base CMDB

Status: IMPLEMENTADA

A Base utiliza dados reais de um export XLSX do OTRS / CMDB.

Atualmente:

- 3.418 links importados;
- ConfigItem# é a chave externa oficial;
- Designação ARION não é única;
- existe histórico de importação;
- existe atualização incremental;
- existe busca;
- existem filtros;
- existe paginação;
- existe drawer de detalhes;
- existem provedores reais;
- existem operadoras e projetos classificados.

O módulo está em:

arion_geo/aplicativos/base_links/

A Base não deve utilizar dados fictícios.

---

# Provedores

Os provedores / ISPs vêm da Base CMDB real.

Informações reais disponíveis:

- nome;
- ConfigItem quando disponível;
- quantidade de links;
- participação na base;
- projetos relacionados;
- operadoras relacionadas;
- UFs relacionadas.

Métricas operacionais de desempenho ainda não são reais.

---

# Mapa

Status: IMPLEMENTADO / EM REFINAMENTO

O mapa utiliza Mapbox GL JS.

Base geográfica:

static/geo/brasil_estados.geojson

Dados reais:

- links;
- UF;
- operadora;
- projeto;
- ISP.

Modos esperados:

- Base;
- Projetos;
- Chamados;
- Reincidência;
- Motivos.

Base e Projetos utilizam CMDB real.

Chamados, reincidência e motivos ainda utilizam dados demonstrativos determinísticos.

Operadoras principais exibidas na interface:

- Todas;
- Claro;
- Vivo;
- Algar.

O mapa deve continuar sendo uma ferramenta de inteligência geográfica,
e não apenas uma visualização estática do CMDB.

---

# Rankings

Status: IMPLEMENTADO

Os ISPs exibidos devem ser provedores reais da Base CMDB.

Dados reais:

- quantidade de links;
- participação;
- projetos;
- operadoras;
- UFs.

Dados demonstrativos temporários:

- chamados;
- SLA;
- reincidência;
- estourados;
- uptime;
- avaliação;
- score;
- tendência.

Quando os tickets OTRS forem integrados,
a fonte demonstrativa deverá ser substituída sem reconstruir a interface.

---

# Dashboard

Status: VISÃO EXECUTIVA

Rota:

/dashboard/

O Dashboard apresenta links, estados atendidos, provedores, distribuição por
operadora, Top Estados e Top Provedores com dados reais da CMDB. Chamados,
reincidências e a série temporal são demonstrativos e usam
`AnalyticsQueryService.dashboard_snapshot()`, compartilhando a fonte do Cockpit.
O recorte nacional de outubro de 2026 deve coincidir entre as duas telas.

O item do menu é:

Dashboard

O Cockpit fica em `/cockpit/` e concentra filtros, comparação, exploração
analítica, drill-down, consultas rápidas e visões salvas.
---

# Cockpit

Status: IMPLEMENTADO

A especificação está em:

features/cockpit.md

O Cockpit trabalha com:

- estado único reconstruído por query params;
- presets de consulta rápida e filtros manuais pelo mesmo fluxo;
- KPIs contextuais, série temporal, distribuição e tabela detalhada;
- consultas salvas privadas por usuário, com abrir/renomear/excluir;
- exportação CSV, XLSX e PDF a partir do mesmo estado de consulta;
- cancelamento de requisição anterior e tratamento de erro com nova tentativa.

## Dados reais

- links;
- ISP;
- operadora;
- projeto;
- UF.

## Dados demonstrativos temporários

- chamados;
- SLA;
- reincidência;
- motivos;
- backlog;
- tempo médio;
- status de tickets.

---

# Tickets OTRS

Status: NÃO INTEGRADO

Ainda não existe integração real de tickets.

Não inventar schema definitivo do OTRS.

A arquitetura deve permitir futuramente trocar:

DemoOperationalAnalyticsSource

por:

OTRSOperationalAnalyticsSource

sem reconstruir o Cockpit.

---

# Tema

Dark/light já existe.

Preferências de tema são persistidas por usuário.

Novas telas devem suportar imediatamente:

- light;
- dark.

---

# Frontend

Stack atual:

- HTML;
- CSS;
- JavaScript vanilla;
- Mapbox GL JS quando necessário.

Não utilizar:

- React;
- Vue;
- SPA;
- frameworks pesados sem necessidade.

---

# Próximas prioridades

1. integração futura dos tickets OTRS;
2. substituição gradual dos indicadores demo quando houver fonte oficial;
3. automação futura da sincronização CMDB por API.

---

# Regra de segurança

Nunca tratar dados demonstrativos como oficiais.

A interface deve informar claramente quando um dado é:

- CMDB REAL;
- DEMONSTRAÇÃO.



---

# Central de Configurações

A Central está disponível em `/configuracoes/` para usuários autenticados e possui
seções de Minha conta, Segurança e Aparência. A edição de conta altera somente
nome, sobrenome e e-mail do usuário atual. Trocas de senha usam os formulários
e validadores do Django e preservam a sessão autenticada.

A preferência light/dark reutiliza `UserPreference`; não há um segundo model de tema.
`/api/preferences/` continua atendendo a leitura e atualização da preferência.
MFA e gerenciamento de sessões ainda não estão implementados.


---

# RBAC e Data Scope

A Central possui administra??o protegida por permiss?es Django em
`/configuracoes/administracao/usuarios/`, `/configuracoes/administracao/grupos/` e
`/configuracoes/administracao/escopos/`. Os perfis
iniciais s?o Administrador do Sistema, Gestor, Analista NOC e Consulta / Auditoria.
`bootstrap_access` ? idempotente; usu?rios ativos legados sem grupo recebem
Analista NOC na migra??o/bootstrap para preservar o acesso funcional. Superusers
continuam com bypass t?cnico e escopo global impl?cito.

`UserDataScope` separa universo de dados das permiss?es funcionais. `ALL` permite
a base inteira autorizada; `CUSTOM` filtra por Operadora E Projeto, com valores
obtidos do banco. `DataScopeService` aplica o filtro antes das consultas de
Dashboard, Cockpit/API, Mapa, Rankings e Base. Filtros manuais fora do universo
retornam resultados vazios seguros; op??es e agrega??es tamb?m s?o escopadas.
Consulte `ARCHITECTURE.md` e `DATA-SOURCES.md` para as regras detalhadas.

---

# ARI I.A - Preview congelada

A ARI esta disponivel em `/ari/` para usuarios com a permissao `view_ari`.
Conversas, anexos e artefatos pertencem ao usuario e sao removidos com a conversa.
O historico permite criar, abrir, pesquisar, renomear e excluir conversas.

A experiencia Preview apresenta respostas simuladas estruturadas (resumo, tabela,
comparativo, plano de acao, alerta, meta, relatorio e dashboard), acoes rapidas e
fontes futuras identificadas como nao conectadas. Relatorio e mini-dashboard sao
artefatos HTML locais, estaticos e controlados por templates; todos os indicadores,
graficos e tabelas estao identificados como dados demonstrativos.

Anexos aceitam PDF, XLSX, CSV, TXT, DOCX e imagens em armazenamento privado, com
validacao de extensao, MIME, assinatura/conteudo, nome e limite configuravel de
20 MB por arquivo. Downloads exigem autenticacao e pertencimento a conversa. O
conteudo anexado nao e analisado nesta versao Preview.

A ARI permanece sem integracao com LLM, APIs externas, OTRS ou CMDB. Nenhum dado
real e consultado para compor respostas, relatorios ou dashboards demonstrativos.


## Auditoria

`/configuracoes/administracao/auditoria/` e uma central administrativa somente
para leitura, protegida pela permissao `view_audit_log`. Registra autenticacao,
alteracoes administrativas, importacao CMDB, visoes salvas do Cockpit e
exportacoes do Cockpit. Busca comum, filtros, paginacao e abertura de detalhes nao
sao auditados. A listagem filtra por periodo, usuario, categoria, acao, modulo e
resultado; o CSV exporta o recorte filtrado e tambem gera um evento
`AUDIT_EXPORT`. Metadata e sanitizada pelo `AuditService`; nao ha edicao, limpeza
ou retencao automatica dos eventos. Politica de retencao permanece uma decisao
administrativa futura.
