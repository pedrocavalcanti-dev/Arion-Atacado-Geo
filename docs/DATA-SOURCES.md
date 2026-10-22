# Fontes de dados e escopo

## CMDB oficial

OTRS / CMDB ? a fonte oficial. A base local ? um espelho anal?tico alimentado por
export XLSX. Links, operadoras, projetos, provedores e UFs n?o devem ser
substitu?dos por dados fict?cios.

## M?tricas operacionais

Tickets, status, SLA, reincid?ncia, motivos, backlog e tempos ainda s?o
demonstrativos at? existir integra??o OTRS confirmada. A fonte demo deriva as
estimativas das combina??es CMDB dispon?veis; n?o representa dados oficiais.

## Data Scope

O escopo ? uma regra de autoriza??o aplicada ?s linhas CMDB, n?o uma nova fonte.
`ALL` deixa o universo funcional completo. `CUSTOM` cruza as operadoras e projetos
permitidos. Como indicadores demo s?o derivados das linhas CMDB, Dashboard e
Cockpit tamb?m calculam seus valores apenas com as combina??es que sobreviveram
ao escopo. Mapa, Rankings e Base agregam, listam e oferecem filtros apenas sobre
essas mesmas linhas.

O escopo ? imposto no backend antes de consultas, filtros, agrega??es e
pagina??o. No Cockpit, op??es e resultados usam apenas linhas permitidas; um
filtro solicitado fora do escopo resulta em valor zero/sem distribui??o. No Mapa,
o agregado filtrado fica vazio.

O endpoint de exportação do Cockpit chama o mesmo serviço analítico da tela com o
usuário autenticado. Portanto, CSV, XLSX e PDF são gerados a partir das linhas
CMDB já limitadas pelo Data Scope vigente.
