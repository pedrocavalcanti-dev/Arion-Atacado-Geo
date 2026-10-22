# Arquitetura de acesso

## RBAC

Autoriza??o funcional usa `django.contrib.auth` Groups e Permissions. Permiss?es
customizadas, declaradas em `UserDataScope`, s?o apresentadas na Central agrupadas
por m?dulo. As rotas usam `access_required` e o backend do Django; negar acesso ?
rota direta retorna HTTP 403. Superusers mant?m bypass t?cnico.

Os perfis iniciais s?o `Administrador do Sistema`, `Gestor`, `Analista NOC` e
`Consulta / Auditoria`. O comando `python gerenciar.py bootstrap_access` provisiona
e sincroniza esses perfis de forma idempotente. O sinal post-migrate executa o
mesmo bootstrap. Usu?rios ativos preexistentes sem grupo recebem `Analista NOC`
para preservar o acesso anterior; usu?rios comuns criados sem perfil tamb?m
recebem esse acesso operacional inicial. Administradores podem selecionar
outro perfil na cria??o/edi??o.

## Data Scope

`UserDataScope` ? um v?nculo OneToOne com o usu?rio e ? independente dos grupos:
Group/Permission define o que a pessoa pode fazer; Data Scope define quais
registros CMDB podem aparecer. O modo `ALL` permite todo o universo autorizado.
O modo `CUSTOM` limita a `Operadora` e `Projeto` selecionados. Os filtros s?o
combinados por interse??o: um registro precisa pertencer a uma operadora E a um
projeto permitidos. Listas vazias produzem um universo vazio. Superusers t?m
escopo global impl?cito.

`DataScopeService.filter_queryset()` aplica a restri??o na QuerySet CMDB antes de
busca, filtros da requisi??o, agrega??o e pagina??o. Dashboard, Cockpit, Mapa,
Rankings e Base reutilizam essa camada. Filtros manuais fora do escopo retornam
resultado vazio seguro; options anal?ticas e facetas s?o geradas do universo
permitido. A autoriza??o RBAC continua sendo validada separadamente em cada rota.

A Central de Configura??es ? uma interface normal da aplica??o em
`/configuracoes/`; `/admin/` permanece apenas como ferramenta t?cnica/emergencial.

## Cockpit analítico

O `AnalyticsQueryService` normaliza KPIs, série temporal, distribuição e tabela
detalhada para o Cockpit. Consulta e exportação chamam o mesmo serviço com o
usuário autenticado; `DataScopeService` restringe a QuerySet CMDB antes da
agregação. Consultas salvas persistem apenas a configuração privada do usuário e
são executadas novamente sob o escopo vigente.
