# Feature: Rankings

Status: implementado

Rota:

/rankings/

---

# Objetivo

Analisar provedores / ISPs que atendem a operação.

---

# Participantes

Sempre utilizar provedores reais da Base CMDB.

Não utilizar nomes fictícios se o ISP não existe na Base.

---

# Dados reais

- nome;
- ConfigItem do ISP quando disponível;
- links;
- participação;
- projetos;
- operadoras;
- UFs.

---

# Dados demonstrativos

Até integração dos tickets:

- chamados;
- SLA;
- reincidência;
- estourados;
- uptime;
- avaliação;
- score;
- tendência.

---

# Critérios

Pode suportar:

- Geral;
- Mais links;
- Melhor SLA;
- Pior SLA;
- Mais chamados;
- Mais reincidência;
- Mais estourados;
- Melhor avaliação.

Mais links é uma métrica real.

Critérios de atendimento são demonstrativos enquanto não houver tickets.

---

# Drawer

O detalhe de ISP deve separar:

BASE REAL

de:

PERFORMANCE DEMONSTRATIVA.

---

# Futuro

A interface deve continuar funcionando quando a fonte demo for trocada por tickets reais OTRS.

