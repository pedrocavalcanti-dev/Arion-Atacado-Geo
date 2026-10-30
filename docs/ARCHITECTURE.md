# Arquitetura

OTRS / CMDB
    ↓
Sincronização
    ↓
Espelho local Django
    ↓
Services / Analytics
    ↓
Base / Mapa / Rankings / Dashboard

## Atual

CMDB:
importação XLSX.

## Futuro

CMDB:
API / Web Service OTRS.

Tickets:
API ou export OTRS.

## Princípio

A fonte externa continua sendo a verdade.

O banco local serve para:

- performance
- agregação
- pesquisa
- análise