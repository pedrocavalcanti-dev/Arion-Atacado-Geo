# Rankings de Operadoras e Links

O ranking agrega `CMDBOperatorMirror` e Links atuais do mirror, alem de tickets relacionados no periodo por data de criacao. Metricas transparentes: quantidade de Links, tickets distintos, business-open corrente, Links afetados, Links reincidentes (2+ tickets distintos), tickets por Link e percentual de Links afetados. Nao existe score composto ou dados demo.

Um Ticket com varios CIs conta uma vez no KPI geral, em cada Link relacionado e em cada Operadora representada. Data Scope e aplicado antes da agregacao; em CUSTOM, ticket sem Link permitido nao aparece. Filtros de data usam `date_from`/`date_to`.
