# Cockpit

`AnalyticsQueryService` consulta mirrors locais e aplica Data Scope antes dos filtros. Metricas suportadas: Links, tickets criados, tickets abertos (estado corrente), tickets resolvidos/encerrados, Links reincidentes e backlog atual. Dimensoes: mes, Operadora, Projeto legado, ISP, UF, status, SLA por nome e servico.

Periodo usa mes de `source_created_at`; backlog e business-open refletem estados atuais, nao snapshots passados. Tickets contam distinct no total; um ticket pode integrar a distribuicao de cada Link associado. SLA cumprido, tempo medio e motivos nao sao inventados.

Exportacao chama o mesmo servico/query e mesmo escopo da interface. Consultas salvas guardam filtros, nao snapshots, e sao recalculadas no escopo atual.
