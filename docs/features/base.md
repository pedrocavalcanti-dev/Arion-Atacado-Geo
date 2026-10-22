# Feature: Base

Status: implementada

Rota principal:

/base/

---

# Objetivo

Fornecer uma visão pesquisável e estruturada do espelho local da Base oficial OTRS / CMDB.

OTRS / CMDB continua sendo a fonte da verdade.

---

# Fonte

Atual:

Export XLSX do CMDB.

Futuro:

API / Web Service OTRS.

A troca da fonte não deve exigir reconstrução da interface.

---

# Identificador oficial

Usar:

ConfigItem#

como chave externa.

Não usar Designação ARION como unique key.

---

# Recursos

A Base possui:

- importação XLSX;
- análise antes da confirmação;
- atualização de registros existentes;
- busca;
- filtros;
- paginação;
- drawer;
- histórico;
- provedores;
- operadoras;
- projetos;
- UFs.

---

# Visões

A Base pode possuir duas visões:

## Links

Circuitos individuais.

## Por provedor

Agregação por ISP.

---

# Pesquisa

Deve suportar campos como:

- Designação ARION;
- ConfigItem;
- ISP;
- cidade;
- UF;
- contrato;
- circuito.

---

# Dados sensíveis

Não expor:

- senha PPPoE;
- credenciais;
- secrets.

Campos sensíveis não devem ir para frontend ou APIs comuns.

---

# Integração

Base alimenta:

- Mapa;
- Dashboard / Cockpit;
- Rankings;
- futuras análises.

