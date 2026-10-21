(() => {
  const number = new Intl.NumberFormat("pt-BR");
  const cache = new Map();
  const load = async url => { if (!cache.has(url)) cache.set(url, fetch(url).then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })); return cache.get(url); };
  const api = {
    async load(urls) { const [base, history, projects, reasons] = await Promise.all([load(urls.base),load(urls.history),load(urls.projects),load(urls.reasons)]); return {base,history,projects,reasons}; },
    aggregate(data, filters) {
      const rows = data.history.records.filter(r => r.period === filters.period && (filters.operator === "all" || r.operator === filters.operator) && (filters.project === "all" || r.project === filters.project));
      
      const result = {};
      for (const r of rows) { const x=result[r.uf] ||= {claro:0,vivo:0,algar:0,total_links:0,chamados:0,reincidentes:0,motivos:{}}; x.chamados+=r.tickets; x.reincidentes+=r.recurrences; x[r.operator]+=r.links; x.total_links+=r.links; for(const [k,v] of Object.entries(r.reasons)) x.motivos[k]=(x.motivos[k]||0)+v; }

      return result;
    },
    formatNumber(value) { return number.format(value); },
  };
  // The UI depends on this small contract; a future API adapter can expose the same load/aggregate methods.
  window.ArionGeoData = api;
})();
