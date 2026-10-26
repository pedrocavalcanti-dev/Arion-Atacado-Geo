(() => {
  const number = new Intl.NumberFormat("pt-BR");
  const months = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out"];
  const reasons = [
    ["falha_massiva", "Falha massiva"], ["rompimento_fibra", "Rompimento de fibra"],
    ["troca_drop", "Troca de drop"], ["equipamento", "Equipamento"],
    ["falha_eletrica", "Falha elétrica"], ["sem_intervencao", "Sem intervenção"], ["outros", "Outros"],
  ];
  const cache = new Map();
  const load = async url => {
    if (!cache.has(url)) cache.set(url, fetch(url).then(response => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    }));
    return cache.get(url);
  };
  function operatorKey(name) {
    const normalized = String(name || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("pt-BR");
    if (normalized.includes("claro")) return "claro";
    if (normalized.includes("vivo")) return "vivo";
    if (normalized.includes("algar")) return "algar";
    return "other";
  }
  function stableValue(text) {
    let hash = 2166136261;
    for (const character of text) hash = Math.imul(hash ^ character.charCodeAt(0), 16777619) >>> 0;
    return hash / 4294967295;
  }
  function reasonCounts(tickets, seed) {
    const rawWeights = reasons.map(([id], index) => 12 + Math.floor(stableValue(`${seed}:${id}:${index}`) * 15));
    const totalWeight = rawWeights.reduce((sum, value) => sum + value, 0);
    const counts = Object.fromEntries(reasons.map(([id], index) => [id, Math.floor(tickets * rawWeights[index] / totalWeight)]));
    let remainder = tickets - Object.values(counts).reduce((sum, value) => sum + value, 0);
    for (let index = 0; remainder > 0; index = (index + 1) % reasons.length, remainder--) counts[reasons[index][0]]++;
    return counts;
  }
  function adaptCMDB(data) {
    if (!Array.isArray(data.combinations) || !data.states) throw new Error("A API CMDB não retornou combinações de operadora/projeto para o mapa.");
    const projects = { all: [], claro: [], vivo: [], algar: [] };
    const seen = Object.fromEntries(Object.keys(projects).map(key => [key, new Map()]));
    const combos = data.combinations.map(row => {
      const operator = operatorKey(row.operator);
      const project = row.project_id == null ? "unclassified" : String(row.project_id);
      const projectName = row.project || "Não classificado";
      if (row.project_id != null) {
        seen.all.set(project, projectName);
        if (operator !== "other") seen[operator].set(project, projectName);
      }
      return { ...row, operator, project, projectName };
    });
    for (const key of Object.keys(seen)) {
      projects[key] = [...seen[key]].map(([id, name]) => [id, name, 0]).sort((a, b) => a[1].localeCompare(b[1], "pt-BR"));
    }
    const periods = months.map((label, index) => ({ id: `2026-${String(index + 1).padStart(2, "0")}`, label: `${label}/26` }));
    const historyRecords = [];
    for (const row of combos) {
      for (const period of periods) {
        const seed = `${row.uf}:${row.operator}:${row.project}:${period.id}`;
        const rate = 0.065 + stableValue(`${seed}:rate`) * 0.105;
        const tickets = row.links ? Math.round(row.links * rate) : 0;
        const recurrences = Math.min(tickets, Math.round(tickets * (0.14 + stableValue(`${seed}:repeat`) * 0.2)));
        historyRecords.push({
          period: period.id, operator: row.operator, project: row.project, projectName: row.projectName, uf: row.uf,
          provider: row.provider, unclassified: row.operator === "other" || row.project === "unclassified" ? row.links : 0,
          links: row.links, tickets, recurrences, reasons: reasonCounts(tickets, seed),
        });
      }
    }
    return {
      base: { operation: "CMDB real", records: combos },
      history: { periods, records: historyRecords },
      projects,
      reasons: reasons.map(([id, label]) => ({ id, label })),
      source: "cmdb",
    };
  }
  const api = {
    async load(urls) {
      if (urls.api) {
        const cmdb = await load(urls.api);
        return adaptCMDB(cmdb);
      }
      const [base, history, projects, reasons] = await Promise.all([load(urls.base), load(urls.history), load(urls.projects), load(urls.reasons)]);
      return { base, history, projects, reasons, providersByState: {}, source: "demo" };
    },
    aggregate(data, filters) {
      const scopedRows = data.history.records.filter(row => row.period === filters.period
        && (filters.project === "all" || row.project === filters.project));
      const rows = scopedRows.filter(row => filters.operator === "all" || row.operator === filters.operator);
      const result = {};
      const operatorTotals = {};
      for (const row of scopedRows) {
        const totals = operatorTotals[row.uf] ||= { claro: 0, vivo: 0, algar: 0, other: 0 };
        totals[row.operator] = (totals[row.operator] || 0) + row.links;
      }
      for (const row of rows) {
        const state = result[row.uf] ||= { claro: 0, vivo: 0, algar: 0, other: 0, unclassified: 0, total_links: 0, chamados: 0, reincidentes: 0, motivos: {}, providers: {}, projects: {} };
        state[row.operator] = (state[row.operator] || 0) + row.links;
        state.total_links += row.links;
        state.chamados += row.tickets;
        state.reincidentes += row.recurrences;
        state.unclassified += row.unclassified || 0;
        for (const [reason, count] of Object.entries(row.reasons)) state.motivos[reason] = (state.motivos[reason] || 0) + count;
        if (row.provider) state.providers[row.provider] = (state.providers[row.provider] || 0) + row.links;
        if (row.project !== "unclassified") state.projects[row.projectName || row.project] = (state.projects[row.projectName || row.project] || 0) + row.links;
      }
      for (const [uf, totals] of Object.entries(operatorTotals)) if (result[uf]) result[uf].allOperators = totals;
      return result;
    },
    formatNumber(value) { return number.format(value); },
  };
  window.ArionGeoData = api;
})();
