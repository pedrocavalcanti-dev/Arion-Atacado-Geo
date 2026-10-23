# Mapa

O Mapa usa Links atuais de `CMDBLinkMirror`, Operadoras locais e `legacy_project` apenas como filtro transitorio. A API aplica Data Scope antes de filtros e agrega por UF. Nao consulta CMDB/OTRS durante requests.

Filtros de periodo usam criacao do Ticket (`source_created_at`). Tickets abertos e Links afetados usam status business-open atual dentro do conjunto de tickets selecionado. O mesmo ticket conta uma vez no total por UF, e cada Link associado participa da contagem por Link. Geometrias estaduais sao assets locais existentes; coordenadas nao sao inventadas.
