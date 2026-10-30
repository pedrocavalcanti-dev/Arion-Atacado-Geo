# Cockpit

Status: planejado

## Objetivo

Transformar /dashboard/ em Cockpit operacional.

## Dados

Real:
- links
- ISP
- operadora
- projeto
- UF

Demo:
- tickets
- SLA
- reincidência
- motivos

## V1

- filtros globais
- período
- comparação
- cards reativos
- gráfico temporal
- breakdown
- query engine
- consultas rápidas
- saved views

## Métricas

- links
- tickets
- open_tickets
- closed_tickets
- recurrences
- sla_met
- sla_missed
- backlog
- avg_resolution_time

## Dimensões

- month
- operator
- project
- provider
- uf
- reason
- status
- sla_status

## Query engine

Frontend não envia SQL.

Input:
- metric
- group_by
- filters
- period
- compare_to

## Futuro

Trocar DemoOperationalAnalyticsSource por OTRSOperationalAnalyticsSource.