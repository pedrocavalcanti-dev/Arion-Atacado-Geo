(() => {
  const root = document.querySelector("[data-map-config]");
  if (!root) return;

  const mapElement = document.getElementById("brazil-map");
  const message = root.querySelector("[data-map-message]");
  const messageTitle = root.querySelector("[data-message-title]");
  const messageDescription = root.querySelector("[data-message-description]");
  const spinner = root.querySelector("[data-map-spinner]");
  const errorBox = root.querySelector("[data-map-error]");
  const errorDetail = root.querySelector("[data-map-error-detail]");
  const globalLoading = document.querySelector("[data-global-loading]");
  const panel = root.querySelector("[data-state-panel]");
  const breadcrumb = document.querySelector(".geo-breadcrumb");
  const flagsScript = document.getElementById("state-flags-data");
  const stateFlags = flagsScript ? JSON.parse(flagsScript.textContent) : {};
  const numberFormat = new Intl.NumberFormat("pt-BR");

  /* Paleta do mapa para dark e light (operadoras preservadas, contraste próprio por tema). */
  const mapThemes = {
    dark: {
      background: "#080909",
      hoverFill: "#b9c1bd",
      defaultFill: "#252929",
      borderColor: "rgba(231,237,233,0.28)",
      borderHover: "#c1cbc5",
      selectionColor: "#e3e8e5",
      labelColor: "#f1f3f1",
      labelHalo: "rgba(8,10,10,0.92)",
      operators: {
        claro: { base: "#874746", low: "#171a1a", mid: "#593130", high: "#cf7771" },
        vivo: { base: "#69527b", low: "#171a1a", mid: "#49375a", high: "#a987c4" },
        algar: { base: "#58735f", low: "#171a1a", mid: "#3c5945", high: "#8eaf91" },
      },
      metrics: { calls: { low: "#1a1b1b", mid: "#8f6856", high: "#d18a69" }, repeat: { low: "#1a1b1b", mid: "#70566f", high: "#bc86a9" }, motives: { low: "#1a1b1b", mid: "#765c72", high: "#b68bb1" } },
    },
    light: {
      background: "#e9ece8",
      hoverFill: "#758079",
      defaultFill: "#d8ddd9",
      borderColor: "rgba(28,38,32,0.26)",
      borderHover: "#2f3b33",
      selectionColor: "#17211a",
      labelColor: "#172019",
      labelHalo: "rgba(236,239,236,0.94)",
      operators: {
        claro: { base: "#bd746f", low: "#e6dcd9", mid: "#c88984", high: "#9f4b46" },
        vivo: { base: "#937bb0", low: "#e2dde7", mid: "#a28cbd", high: "#675086" },
        algar: { base: "#799b81", low: "#dbe3dc", mid: "#8aa892", high: "#4b7155" },
      },
      metrics: { calls: { low: "#e3e5e1", mid: "#d5a083", high: "#bd674b" }, repeat: { low: "#e5e1e7", mid: "#b69ab5", high: "#865f85" }, motives: { low: "#e5e1e7", mid: "#b69ab5", high: "#765b82" } },
    },
  };

  const operatorNames = { claro: "Claro", vivo: "Vivo", algar: "Algar" };
  const modeNames = { base: "links", projects: "links do projeto", calls: "chamados", repeat: "reincidentes", motives: "ocorrências" };
  const motiveNames = { falha_massiva: "Falha massiva", rompimento_fibra: "Rompimento de fibra", troca_drop: "Troca de drop", equipamento: "Equipamento", cabo_desconectado: "Cabo desconectado", falha_eletrica: "Falha elétrica", sem_intervencao: "Sem interven\u00e7\u00e3o", outros: "Outros" };
  const stateLabels = {
    AC: [-70.4, -9.3], AL: [-36.2, -9.6], AM: [-63.8, -4.2], AP: [-51.8, 1.1],
    BA: [-41.5, -12.1], CE: [-39.4, -5.1], DF: [-47.9, -15.8], ES: [-40.7, -19.5],
    GO: [-49.5, -16.0], MA: [-45.1, -5.5], MG: [-44.5, -18.5], MS: [-54.6, -20.5],
    MT: [-56.2, -13.3], PA: [-52.0, -4.2], PB: [-36.8, -7.1], PE: [-37.5, -8.4],
    PI: [-42.7, -7.4], PR: [-51.0, -24.7], RJ: [-42.3, -22.4], RN: [-36.4, -5.7],
    RO: [-63.0, -10.8], RR: [-61.4, 2.1], RS: [-53.0, -30.3], SC: [-50.5, -27.3],
    SE: [-37.2, -10.5], SP: [-48.5, -22.3], TO: [-48.3, -10.4],
  };
  const brazilBounds = [[-76.0, -37.0], [-32.0, 8.0]];
  const sourceId = "brasil-estados";
  const fillLayerId = "uf-preenchimento";
  const lineLayerId = "uf-contorno";
  const selectionLayerId = "uf-selecao";
  const labelLayerId = "uf-siglas";

  let map = null;
  let states = null;
  let stateGeometryBounds = null;
  let demoData = null;
  let demoStore = null;
  const MAP_STATE_KEY = "arion-geo-map-state-v1";
  const state = { operator: "all", project: "all", period: "2026-10", metric: "base", reason: "all", selectedUF: null, nationalPanelCollapsed: false, nationalPanelTab: "summary" };
  let mapInteractionsBound = false;
  let searchOptions = [];
  let searchActiveIndex = -1;
  let hoveredCode = null;
  let popup = null;
  let tooltipContent = null;
  let mapLoaded = false;
  let uiBound = false;

  function currentThemePalette() {
    return document.documentElement.dataset.theme === "light" ? mapThemes.light : mapThemes.dark;
  }

  function setLoading(isLoading) {
    if (globalLoading) globalLoading.hidden = !isLoading;
  }

  function setMessage(title, description, isError = false) {
    messageTitle.textContent = title;
    messageDescription.textContent = description;
    message.classList.toggle("is-error", isError);
    spinner.hidden = isError;
    message.hidden = false;
  }

  function hideMessage() {
    message.hidden = true;
  }

  function showError(detail) {
    setLoading(false);
    hideMessage();
    errorDetail.textContent = detail || "Verifique a conexão e tente novamente.";
    errorBox.hidden = false;
  }

  function clearError() {
    errorBox.hidden = true;
  }

  function dominantOperator(data) {
    const dominant = ["claro", "vivo", "algar"].reduce((current, operator) => (
      data[operator] > data[current] ? operator : current
    ), "claro");
    return data[dominant] > 0 ? dominant : "other";
  }

  function saveMapState() {
    // Future: synchronize map preferences with the user's profile.
    try {
      localStorage.setItem(MAP_STATE_KEY, JSON.stringify({ version: 1, ...state }));
    } catch (_) {
      // Storage may be unavailable in private browsing; map use can continue without persistence.
    }
  }

  function loadMapState() {
    try {
      const raw = localStorage.getItem(MAP_STATE_KEY);
      if (!raw) return;
      const saved = JSON.parse(raw);
      if (!saved || saved.version !== 1 || typeof saved !== "object") throw new Error("Unsupported map state");
      const operators = ["all", "claro", "vivo", "algar"];
      const periods = demoStore.history.periods.map(item => item.id);
      const metrics = ["base", "projects", "calls", "repeat", "motives"];
      const reasons = demoStore.reasons.map(item => item.id);
      state.operator = operators.includes(saved.operator) ? saved.operator : "all";
      state.project = (demoStore.projects[state.operator] || demoStore.projects.all || []).some(item => item[0] === saved.project) ? saved.project : "all";
      state.period = periods.includes(saved.period) ? saved.period : periods[periods.length - 1];
      state.metric = metrics.includes(saved.metric) ? saved.metric : "base";
      state.reason = ["all", ...reasons].includes(saved.reason) ? saved.reason : "all";
      state.selectedUF = typeof saved.selectedUF === "string" && states.features.some(feature => feature.properties.sigla === saved.selectedUF) ? saved.selectedUF : null;
      state.nationalPanelCollapsed = typeof saved.nationalPanelCollapsed === "boolean" ? saved.nationalPanelCollapsed : false;
      state.nationalPanelTab = ["summary", "ranking", "distribution"].includes(saved.nationalPanelTab) ? saved.nationalPanelTab : "summary";
    } catch (_) {
      Object.assign(state, { operator: "all", project: "all", period: "2026-10", metric: "base", reason: "all", selectedUF: null, nationalPanelCollapsed: false, nationalPanelTab: "summary" });
      try { localStorage.removeItem(MAP_STATE_KEY); } catch (_) { /* Ignore unavailable storage. */ }
    }
  }

  function syncControlsFromState() {
    document.querySelectorAll("[data-operator]").forEach(button => {
      const active = button.dataset.operator === state.operator;
      button.classList.toggle("is-selected", active);
      button.setAttribute("aria-pressed", String(active));
    });
    document.querySelectorAll("[data-mode]").forEach(button => {
      const active = button.dataset.mode === state.metric;
      button.classList.toggle("is-selected", active);
      button.setAttribute("aria-pressed", String(active));
    });
    const period = document.querySelector("[data-period-filter]");
    const project = document.querySelector("[data-project-filter]");
    const motive = document.querySelector("[data-motive-filter]");
    period.disabled = ["base", "projects"].includes(state.metric);
    [...period.options].forEach(option => { option.textContent = period.disabled && option.value === state.period ? "Atual" : (option.dataset.label || option.textContent); });
    period.value = state.period;
    project.value = state.project;
    motive.value = state.reason;
    document.querySelector("[data-motives-select]").hidden = state.metric !== "motives";
    root.querySelectorAll("[data-national-tab]").forEach(tab => {
      tab.setAttribute("aria-selected", String(tab.dataset.nationalTab === state.nationalPanelTab));
      tab.tabIndex = tab.dataset.nationalTab === state.nationalPanelTab ? 0 : -1;
    });
    setNationalCollapsed(state.nationalPanelCollapsed, false);
  }

  function populatePeriodAndProject() {
    const periodSelect = document.querySelector("[data-period-filter]");
    periodSelect.innerHTML = demoStore.history.periods.map(p => `<option value="${p.id}" data-label="${p.label}">${p.label}</option>`).join("");
    updateProjectOptions();
    periodSelect.value = state.period;
    syncControlsFromState();
  }

  function updateProjectOptions() {
    const select = document.querySelector("[data-project-filter]");
    const projects = state.operator === "all" ? (demoStore.projects.all || []) : (demoStore.projects[state.operator] || []);
    select.innerHTML = '<option value="all">Todos</option>' + projects.map(([id,label]) => `<option value="${escapeTooltip(id)}">${escapeTooltip(label)}</option>`).join("");
    if (!projects.some(item => item[0] === state.project)) state.project = "all";
    select.value = state.project;
  }

  function refreshGeoView() {
    if (!demoStore) return;
    demoData = window.ArionGeoData.aggregate(demoStore, state);
    saveMapState();
    const context = document.querySelector("[data-map-context]");
    if (context) context.textContent = buildMapContext(state);
    for (const feature of states.features) demoData[feature.properties.sigla] ||= { claro:0,vivo:0,algar:0,total_links:0,chamados:0,reincidentes:0,motivos:{} };
    hideStateTooltip();
    applyOperatorFilter();
  }

  function metricValue(data) {
    if (state.metric === "projects") return data.total_links;
    if (state.metric === "calls") return data.chamados;
    if (state.metric === "repeat") return data.reincidentes;
    if (state.metric === "motives") return state.reason === "all"
      ? Object.values(data.motivos || {}).reduce((sum, value) => sum + value, 0)
      : (data.motivos?.[state.reason] || 0);
    return data.total_links;
  }

  function metricMaximum() {
    return Math.max(1, ...Object.values(demoData || {}).map(metricValue));
  }

  function makeDisplayCollection() {
    const totals = { claro: 1, vivo: 1, algar: 1 };
    Object.values(demoData).forEach((data) => {
      totals.claro = Math.max(totals.claro, data.claro);
      totals.vivo = Math.max(totals.vivo, data.vivo);
      totals.algar = Math.max(totals.algar, data.algar);
    });

    return {
      type: "FeatureCollection",
      features: states.features.map((feature) => {
        const code = feature.properties.sigla;
        const metrics = demoData[code];
        const dominant = dominantOperator(metrics);
        const activeCount = state.operator === "all" ? metrics.total_links : metrics[state.operator];
        const intensity = ["base", "projects"].includes(state.metric)
          ? state.operator === "all" ? 1 : Math.sqrt(activeCount / totals[state.operator])
          : Math.sqrt(metricValue(metrics) / metricMaximum());
        return {
          ...feature,
          id: code,
          properties: {
            ...feature.properties,
            ...metrics,
            dominante: dominant,
            valor_metrica: metricValue(metrics),
            intensidade: intensity,
            selecionado: code === state.selectedUF,
            ha_selecao: Boolean(state.selectedUF),
          },
        };
      }),
    };
  }

  function colorExpression(palette = currentThemePalette()) {
    const ops = palette.operators;
    if (!["base", "projects"].includes(state.metric)) {
      const scale = palette.metrics[state.metric];
      return ["interpolate", ["linear"], ["get", "intensidade"], 0, scale.low, 0.45, scale.mid, 1, scale.high];
    }
    if (state.operator === "all") {
      return ["match", ["get", "dominante"],
        "claro", ops.claro.base,
        "vivo", ops.vivo.base,
        "algar", ops.algar.base,
        palette.defaultFill];
    }
    const scale = ops[state.operator];
    return ["interpolate", ["linear"], ["get", "intensidade"], 0, scale.low, 0.35, scale.mid, 1, scale.high];
  }

  function fillColorExpression(palette = currentThemePalette()) {
    return [
      "case",
      ["boolean", ["get", "selecionado"], false], colorExpression(palette),
      ["boolean", ["feature-state", "hover"], false], palette.hoverFill,
      colorExpression(palette),
    ];
  }

  function applyOperatorFilter() {
    if (!map || !map.getSource(sourceId) || !demoData || !states) return;
    if (hoveredCode) map.setFeatureState({ source: sourceId, id: hoveredCode }, { hover: false });
    const palette = currentThemePalette();
    map.setPaintProperty(fillLayerId, "fill-color-transition", { duration: 280, delay: 0 });
    map.getSource(sourceId).setData(makeDisplayCollection());
    map.setPaintProperty(fillLayerId, "fill-color", fillColorExpression(palette));
    map.setPaintProperty(fillLayerId, "fill-opacity", [
      "case",
      ["boolean", ["get", "selecionado"], false], 0.96,
      ["boolean", ["get", "ha_selecao"], false], 0.38,
      0.9,
    ]);
    updateLegend();
    if (state.selectedUF) updateStatePanel(state.selectedUF);
    renderNationalPanel();
  }

  /* Atualiza imediatamente todas as camadas do mapa ao alternar tema (sem F5 ou recriar Mapbox). */
  function applyMapTheme(theme) {
    const mode = theme === "light" ? "light" : "dark";
    const palette = mapThemes[mode];
    root.dataset.mapTheme = mode;
    updateLegend();
    if (!map || !mapLoaded) return;
    if (map.getLayer("fundo-arion")) {
      map.setPaintProperty("fundo-arion", "background-color", palette.background);
    }
    if (map.getLayer(fillLayerId)) {
      map.setPaintProperty(fillLayerId, "fill-color", fillColorExpression(palette));
    }
    if (map.getLayer(lineLayerId)) {
      map.setPaintProperty(lineLayerId, "line-color", [
        "case",
        ["boolean", ["feature-state", "hover"], false], palette.borderHover,
        palette.borderColor,
      ]);
    }
    if (map.getLayer(selectionLayerId)) {
      map.setPaintProperty(selectionLayerId, "line-color", palette.selectionColor);
    }
    if (map.getLayer(labelLayerId)) {
      map.setPaintProperty(labelLayerId, "text-color", palette.labelColor);
      map.setPaintProperty(labelLayerId, "text-halo-color", palette.labelHalo);
    }
    map.triggerRepaint();
  }

  function updateLegend() {
    const legend = document.querySelector("[data-legend]");
    if (!legend) return;
    if (!["base", "projects"].includes(state.metric)) {
      legend.classList.add("geo-legend--scale");
      legend.innerHTML = `<span class="legend-scale-label">Menos ${modeNames[state.metric]}</span><span class="legend-scale legend-scale--${state.metric}"></span><span class="legend-scale-label">Mais</span>`;
      return;
    }
    if (state.operator === "all") {
      legend.classList.remove("geo-legend--scale");
      legend.innerHTML = '<span class="legend-item"><i class="legend-dot legend-dot--claro"></i>Claro</span><span class="legend-item"><i class="legend-dot legend-dot--vivo"></i>Vivo</span><span class="legend-item"><i class="legend-dot legend-dot--algar"></i>Algar</span>';
      return;
    }
    legend.classList.add("geo-legend--scale");
    legend.innerHTML = `<span class="legend-scale-label">Baixa intensidade</span><span class="legend-scale" data-scale="${state.operator}"></span><span class="legend-scale-label">Alta</span><span class="legend-operator">${operatorNames[state.operator]}</span>`;
  }

  function totalsByField(field) {
    return Object.values(demoData || {}).reduce((sum, row) => sum + (row[field] || 0), 0);
  }

  function selectedMetricLabel() {
    if (state.metric === "projects") return "Links do projeto";
    if (state.metric === "calls") return "Chamados";
    if (state.metric === "repeat") return "Reincidentes";
    if (state.metric === "motives") return state.reason === "all" ? "Ocorrencias" : motiveNames[state.reason];
    return "Links";
  }

  function renderNationalPanel() {
    const view = root.querySelector("[data-national-view]");
    if (!view || !demoData || !states) return;
    const stateRows = states.features.map((feature) => ({
      code: feature.properties.sigla,
      name: feature.properties.nome,
      feature,
      value: metricValue(demoData[feature.properties.sigla]),
    }));
    const byLinks = [...stateRows].sort((a, b) => demoData[b.code].total_links - demoData[a.code].total_links);
    const byCalls = [...stateRows].sort((a, b) => demoData[b.code].chamados - demoData[a.code].chamados);
    const totals = {
      links: totalsByField("total_links"),
      calls: totalsByField("chamados"),
      repeat: totalsByField("reincidentes"),
      states: stateRows.filter(row => row.value || demoData[row.code].total_links).length,
      operators: ["claro", "vivo", "algar"].filter(key => totalsByField(key) > 0).length,
      projects: new Set(demoStore.history.records.filter(row => row.period === state.period && (state.operator === "all" || row.operator === state.operator) && (state.project === "all" || row.project === state.project) && row.project !== "unclassified").map(row => row.project)).size,
      providers: new Set(Object.values(demoData).flatMap(row => Object.keys(row.providers || {}))).size,
      unclassified: totalsByField("unclassified"),
    };
    view.setAttribute("aria-labelledby", `national-tab-${state.nationalPanelTab}`);
    document.querySelectorAll("[data-national-tab]").forEach((tab) => {
      tab.setAttribute("aria-selected", String(tab.dataset.nationalTab === state.nationalPanelTab));
      tab.tabIndex = tab.dataset.nationalTab === state.nationalPanelTab ? 0 : -1;
    });

    if (state.nationalPanelTab === "summary") {
      view.innerHTML = `<div class="national-kpis"><div><strong>${numberFormat.format(totals.links)}</strong><span>Links · CMDB real</span></div><div><strong>${totals.states}</strong><span>UFs atendidas</span></div><div><strong>${totals.operators}</strong><span>Operadoras</span></div><div><strong>${totals.projects}</strong><span>Projetos</span></div><div><strong>${numberFormat.format(totals.providers)}</strong><span>Provedores</span></div><div><strong>${numberFormat.format(totals.unclassified)}</strong><span>Não classificados</span></div><div><strong>${numberFormat.format(totals.calls)}</strong><span>Chamados · demo</span></div><div><strong>${numberFormat.format(totals.repeat)}</strong><span>Reincidências · demo</span></div></div><div class="national-leaders"><div><span>Maior base</span><strong>${byLinks[0]?.name || "—"}</strong><small>${numberFormat.format(demoData[byLinks[0]?.code]?.total_links || 0)} links reais</small></div><div><span>Mais ${selectedMetricLabel().toLowerCase()}</span><strong>${[...stateRows].sort((a,b)=>b.value-a.value)[0]?.name || "—"}</strong><small>${numberFormat.format([...stateRows].sort((a,b)=>b.value-a.value)[0]?.value || 0)} · ${["base", "projects"].includes(state.metric) ? "CMDB real" : "demo"}</small></div></div>`;
      return;
    }

    if (state.nationalPanelTab === "ranking") {
      const label = selectedMetricLabel();
      const rows = [...stateRows].sort((a, b) => b.value - a.value).slice(0, 5);
      view.innerHTML = `<div class="national-view-heading"><span>Top 5 por ${label.toLowerCase()}</span><span class="demo-inline">${["base", "projects"].includes(state.metric) ? "CMDB real" : "Demonstração"}</span></div><ol class="national-ranking">${rows.map((row, index) => `<li><span class="national-rank-number">${String(index + 1).padStart(2, "0")}</span><img src="${stateFlags[row.code] || ""}" alt="" width="22" height="15" loading="lazy"><span class="national-rank-name">${row.name}</span><strong>${numberFormat.format(row.value)}</strong></li>`).join("")}</ol>`;
      return;
    }

    const measureRecord = record => ["base", "projects"].includes(state.metric) ? record.links : state.metric === "calls" ? record.tickets : state.metric === "repeat" ? record.recurrences : state.reason === "all" ? Object.values(record.reasons).reduce((sum,value)=>sum+value,0) : (record.reasons[state.reason]||0);
    const scopedHistory = demoStore.history.records.filter(record => record.period===state.period && (state.operator==="all" || record.operator===state.operator) && (state.project==="all" || record.project===state.project));
    const distribution = state.operator === "all"
      ? ["claro","vivo","algar","other"].map(key=>({key,name:key==="other"?"Outras / não classificadas":operatorNames[key],value:scopedHistory.filter(record=>record.operator===key).reduce((sum,record)=>sum+measureRecord(record),0)})).filter(item=>item.value>0)
      : (demoStore.projects[state.operator] || demoStore.projects.all || []).map(([id,name])=>({key:id,name,value:scopedHistory.filter(record=>record.project===id).reduce((sum,record)=>sum+measureRecord(record),0)}));
    const totalDistribution = distribution.reduce((sum,item)=>sum+item.value,0);
    view.innerHTML = `<div class="national-view-heading"><span>${state.operator === "all" ? "Distribuição por operadora" : `Projetos ${operatorNames[state.operator]}`}</span><span class="demo-inline">${selectedMetricLabel()} · ${["base", "projects"].includes(state.metric) ? "CMDB real · Atual" : `${periodLabel(state.period)} · Demonstração`}</span></div><div class="national-distribution">${distribution.map((item) => `<div class="national-distribution-row"><span>${state.operator === "all" && ["claro","vivo","algar"].includes(item.key) ? `<i class="operator-swatch operator-swatch--${item.key}"></i>` : ""}${item.name}</span><strong>${totalDistribution ? (item.value / totalDistribution * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) : "0"}%</strong><small>${numberFormat.format(item.value)}</small><i class="national-distribution-track"><b class="operator-fill--${item.key}" data-value="${item.value}" data-max="${totalDistribution}"></b></i></div>`).join("")}</div>`;
    view.querySelectorAll("[data-value][data-max]").forEach((bar) => {
      bar.style.width = `${Math.max(0, Number(bar.dataset.value) / Number(bar.dataset.max) * 100)}%`;
    });
  }

  function setNationalCollapsed(collapsed, persist = true) {
    const national = root.querySelector("[data-national-panel]");
    const collapse = root.querySelector("[data-national-collapse]");
    const expand = root.querySelector("[data-national-expand]");
    const content = root.querySelector("[data-national-content]");
    national.classList.toggle("is-collapsed", collapsed);
    national.setAttribute("aria-hidden", String(collapsed));
    national.inert = collapsed;
    collapse.setAttribute("aria-expanded", String(!collapsed));
    collapse.setAttribute("aria-label", collapsed ? "Expandir resumo nacional" : "Recolher resumo nacional");
    content.setAttribute("aria-hidden", String(collapsed));
    content.inert = collapsed;
    expand.hidden = !collapsed;
    state.nationalPanelCollapsed = collapsed;
    if (persist) saveMapState();
    if (map && mapLoaded) {
      window.requestAnimationFrame(() => {
        if (!map || !mapLoaded) return;
        map.resize();
        if (state.selectedUF) {
          const feature = getStateFeature(state.selectedUF);
          if (feature) fitState(feature);
        } else {
          fitBrazil();
        }
      });
    }
  }

  function normalizeSearch(value) {
    return value.trim().normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("pt-BR");
  }

  function closeSearch() {
    const input = document.querySelector("[data-state-search]");
    const list = document.querySelector("[data-state-search-results]");
    list.hidden = true;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
    searchActiveIndex = -1;
  }

  function renderSearchResults(query) {
    const list = document.querySelector("[data-state-search-results]");
    const input = document.querySelector("[data-state-search]");
    const needle = normalizeSearch(query);
    if (!needle || !states) {
      closeSearch();
      return;
    }
    searchOptions = states.features.filter((feature) => {
      const name = normalizeSearch(feature.properties.nome);
      const code = feature.properties.sigla.toLocaleLowerCase("pt-BR");
      return name.includes(needle) || code.startsWith(needle);
    }).slice(0, 7);
    list.innerHTML = searchOptions.map((feature, index) => `<div id="state-option-${feature.properties.sigla}" class="state-search-option" role="option" aria-selected="${index === searchActiveIndex}" data-search-code="${feature.properties.sigla}"><span>${feature.properties.nome}</span><small>${feature.properties.sigla}</small></div>`).join("");
    list.hidden = searchOptions.length === 0;
    input.setAttribute("aria-expanded", String(searchOptions.length > 0));
  }

  function chooseSearchResult(code) {
    const feature = getStateFeature(code);
    if (!feature) return;
    document.querySelector("[data-state-search]").value = `${feature.properties.sigla} - ${feature.properties.nome}`;
    closeSearch();
    selectState(feature);
  }

  function setFeatureHover(code) {
    if (hoveredCode && map.getSource(sourceId)) {
      map.setFeatureState({ source: sourceId, id: hoveredCode }, { hover: false });
    }
    hoveredCode = code;
    if (hoveredCode && map.getSource(sourceId)) {
      map.setFeatureState({ source: sourceId, id: hoveredCode }, { hover: true });
    }
  }

  function formatNumber(value) {
    return numberFormat.format(Number.isFinite(Number(value)) ? Number(value) : 0);
  }

  function formatDecimal(value) {
    return new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(Number.isFinite(value) ? value : 0);
  }

  function formatPercent(value) {
    return `${new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(Number.isFinite(value) ? value : 0)}%`;
  }

  function formatPeriod(period) {
    return demoStore.history.periods.find(item => item.id === period)?.label || "Per\u00edodo indispon\u00edvel";
  }

  function formatOperator(operator) {
    return operator === "all" ? "Todas" : (operatorNames[operator] || "Todas");
  }

  function formatProject(project) {
    if (project === "all") return "Todos os projetos";
    return (demoStore.projects[state.operator] || demoStore.projects.all || []).find(item => item[0] === project)?.[1] || "Todos os projetos";
  }

  function escapeTooltip(value) {
    return String(value ?? "").replace(/[&<>"']/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);
  }

  function buildMapContext(currentState) {
    const metric = currentState.metric === "motives" && currentState.reason !== "all"
      ? (motiveNames[currentState.reason] || "Motivos")
      : ({ base: "Base", projects: "Projetos", calls: "Chamados", repeat: "Reincid\u00eancia", motives: "Motivos" }[currentState.metric] || "Base");
    const operator = formatOperator(currentState.operator);
    const project = currentState.project === "all" ? "Todos os projetos" : formatProject(currentState.project);
    const real = ["base", "projects"].includes(currentState.metric);
    const date = real ? "Atual" : formatPeriod(currentState.period);
    return `${metric} \u2022 ${operator}${currentState.project !== "all" ? ` / ${project}` : ""} \u2022 ${date} \u2022 ${real ? "CMDB REAL" : "DEMO"}`.toLocaleUpperCase("pt-BR");
  }

  function sumHistory(uf, operator, project, period, field) {
    // CMDB base counts are a single current snapshot; avoid rescanning the
    // month-expanded demo history for every project shown in a tooltip.
    const records = ["base", "projects"].includes(state.metric) ? demoStore.base.records : demoStore.history.records;
    return records.reduce((sum, record) => {
      if (record.uf !== uf || (records === demoStore.history.records && record.period !== period)) return sum;
      if (operator !== "all" && record.operator !== operator) return sum;
      if (project !== "all" && record.project !== project) return sum;
      return sum + (field === "reason" ? (record.reasons[state.reason] || 0) : (record[field] || 0));
    }, 0);
  }

  function buildStateTooltipContent(uf, currentState) {
    const feature = getStateFeature(uf);
    const data = demoData?.[uf];
    const name = feature?.properties?.nome || "Unidade federativa";
    const context = buildMapContext(currentState);
    const heading = `<header class="tooltip-heading"><div><span>${escapeTooltip(uf)}</span><strong>${escapeTooltip(name)}</strong></div></header><div class="tooltip-context">${escapeTooltip(context)}</div>`;
    if (!data) return `<section class="state-tooltip">${heading}<p class="tooltip-empty">Sem registros neste recorte.</p></section>`;

    const metricCount = ["base", "projects"].includes(currentState.metric) ? data.total_links
      : currentState.metric === "calls" ? data.chamados
        : currentState.metric === "repeat" ? data.reincidentes
          : currentState.reason === "all" ? Object.values(data.motivos).reduce((sum, value) => sum + value, 0)
            : (data.motivos[currentState.reason] || 0);
    if (!metricCount) return `<section class="state-tooltip">${heading}<p class="tooltip-empty">Sem registros neste recorte.</p></section>`;
    const main = (value, label) => `<div class="tooltip-primary-metric"><strong>${formatNumber(value)}</strong><span>${escapeTooltip(label)}</span></div>`;
    const line = (label, value) => `<div class="tooltip-data-line"><span>${escapeTooltip(label)}</span><b>${escapeTooltip(value)}</b></div>`;
    let details = "";

    if (["base", "projects"].includes(currentState.metric)) {
      const total = currentState.operator === "all" ? data.total_links : data[currentState.operator];
      details += main(total, "links");
      if (currentState.operator === "all") {
        const operatorTotals = data.allOperators || data;
        const dominant = dominantOperator(operatorTotals);
        details += `<div class="tooltip-operators">${["claro", "vivo", "algar"].map(key => `<div><i class="operator-swatch operator-swatch--${key}"></i>${operatorNames[key]}<strong>${formatNumber(operatorTotals[key] || 0)}</strong></div>`).join("")}</div>`;
        details += line("Operadora predominante", operatorNames[dominant] || "Não classificada");
      } else {
        const selectedProject = currentState.project;
        const candidates = (demoStore.projects[currentState.operator] || demoStore.projects.all || []).map(([id, label]) => ({
          id, label, links: sumHistory(uf, currentState.operator, id, currentState.period, "links"),
        })).sort((left, right) => right.links - left.links);
        const denominator = sumHistory(uf, "all", "all", currentState.period, "links");
        const project = selectedProject === "all" ? candidates[0] : candidates.find(item => item.id === selectedProject);
        if (project?.links) details += line(selectedProject === "all" ? "Projeto predominante" : "Projeto", project.label);
        const share = denominator ? total / denominator * 100 : 0;
        details += line("Participa\u00e7\u00e3o na base da UF", formatPercent(share));
      }
      details += line("Fonte", "CMDB real");
    } else if (currentState.metric === "calls") {
      details += main(data.chamados, "chamados");
      details += line("Links", formatNumber(data.total_links));
      details += line("Chamados / 100 links", formatDecimal(data.total_links ? data.chamados / data.total_links * 100 : 0));
      details += line("Reincidentes", formatNumber(data.reincidentes));
      const principal = Object.entries(data.motivos).sort((left, right) => right[1] - left[1])[0];
      details += line("Principal motivo", principal?.[1] ? motiveNames[principal[0]] : "Sem registros");
    } else if (currentState.metric === "repeat") {
      details += main(data.reincidentes, "reincidentes");
      details += line("Chamados", formatNumber(data.chamados));
      details += line("Taxa de reincid\u00eancia", formatPercent(data.chamados ? data.reincidentes / data.chamados * 100 : 0));
      const periods = demoStore.history.periods;
      const previous = periods[periods.findIndex(item => item.id === currentState.period) - 1];
      if (previous) {
        const previousData = window.ArionGeoData.aggregate(demoStore, { ...currentState, period: previous.id })[uf];
        const delta = data.reincidentes - (previousData?.reincidentes || 0);
        details += line(`Varia\u00e7\u00e3o vs. ${formatPeriod(previous.id)}`, `${delta > 0 ? "+" : ""}${formatNumber(delta)} reincidentes`);
      }
    } else {
      const ranked = Object.entries(data.motivos).sort((left, right) => right[1] - left[1]);
      if (currentState.reason !== "all") {
        const count = data.motivos[currentState.reason] || 0;
        details += main(count, "ocorr\u00eancias");
        details += line("Participa\u00e7\u00e3o nos chamados", formatPercent(data.chamados ? count / data.chamados * 100 : 0));
        details += line("Chamados no per\u00edodo", formatNumber(data.chamados));
      } else {
        const top = ranked.filter(([, value]) => value > 0).slice(0, 3);
        if (top.length) {
          details += main(Object.values(data.motivos).reduce((sum, value) => sum + value, 0), "ocorrências");
          details += line("Principal motivo", motiveNames[top[0][0]] || "Outros");
          details += `<div class="tooltip-operators">${top.map(([key, value]) => `<div>${escapeTooltip(motiveNames[key] || "Outros")}<strong>${formatNumber(value)}</strong></div>`).join("")}</div>`;
        }
      }
    }
    return `<section class="state-tooltip">${heading}${details}</section>`;
  }

  function showStateTooltip(event) {
    const feature = event.features && event.features[0];
    if (!feature) return;
    const code = feature.properties.sigla;
    if (!tooltipContent) {
      tooltipContent = document.createElement("div");
      tooltipContent.setAttribute("aria-label", "Resumo contextual demonstrativo da unidade federativa");
      popup = new mapboxgl.Popup({ closeButton: false, closeOnClick: false, offset: 13, maxWidth: "none", className: "geo-popup" })
        .setDOMContent(tooltipContent);
    }
    const shouldRefresh = code !== hoveredCode || !popup.isOpen();
    if (code !== hoveredCode) setFeatureHover(code);
    if (shouldRefresh) tooltipContent.innerHTML = buildStateTooltipContent(code, state);
    popup.setLngLat(event.lngLat);
    if (!popup.isOpen()) popup.addTo(map);
  }

  function hideStateTooltip() {
    if (hoveredCode) setFeatureHover(null);
    if (popup?.isOpen()) popup.remove();
  }

  function calculateGeometryBounds(geometry) {
    const bounds = [[Infinity, Infinity], [-Infinity, -Infinity]];
    const visit = (coordinates) => {
      if (typeof coordinates[0] === "number") {
        bounds[0][0] = Math.min(bounds[0][0], coordinates[0]);
        bounds[0][1] = Math.min(bounds[0][1], coordinates[1]);
        bounds[1][0] = Math.max(bounds[1][0], coordinates[0]);
        bounds[1][1] = Math.max(bounds[1][1], coordinates[1]);
        return;
      }
      coordinates.forEach(visit);
    };
    visit(geometry.coordinates);
    return bounds;
  }

  function panelPadding() {
    const mobile = window.matchMedia("(max-width: 760px)").matches;
    if (mobile) {
      return { top: 30, right: 25, bottom: Math.min(root.clientHeight - 70, panel.getBoundingClientRect().height + 24), left: 25 };
    }
    const panelWidth = panel.getBoundingClientRect().width || 356;
    return { top: 36, right: Math.round(panelWidth + 28), bottom: 36, left: 42 };
  }

  function fitBrazil(animate = true) {
    if (!map) return;
    const national = root.querySelector("[data-national-panel]");
    const collapsed = national.classList.contains("is-collapsed");
    const panelLeft = window.innerWidth <= 760 ? 12 : window.innerWidth <= 1024 ? 14 : 19;
    const panelWidth = window.innerWidth <= 760
      ? Math.min(270, map.getContainer().clientWidth - 24)
      : 274;
    const leftPadding = collapsed ? 32 : panelLeft + panelWidth + 28;
    const verticalPadding = Math.round(map.getContainer().clientHeight * 0.13);
    const finishFit = () => {
      if (!map || !stateGeometryBounds) return;
      const north = mapboxgl.MercatorCoordinate.fromLngLat([0, stateGeometryBounds[1][1]]).y;
      const south = mapboxgl.MercatorCoordinate.fromLngLat([0, stateGeometryBounds[0][1]]).y;
      const projectedHeight = (south - north) * 512 * (2 ** map.getZoom());
      const targetHeight = map.getContainer().clientHeight * 0.72;
      const targetZoom = map.getZoom() + Math.log2(targetHeight / projectedHeight);
      if (targetZoom < map.getZoom() - 0.01) {
        const cameraZoom = Math.max(map.getMinZoom(), targetZoom);
        if (animate) map.easeTo({ zoom: cameraZoom, duration: 240 });
        else map.jumpTo({ zoom: cameraZoom });
      }
    };
    if (animate) map.once("moveend", finishFit);
    map.fitBounds(brazilBounds, {
      padding: { top: verticalPadding, right: 34, bottom: verticalPadding, left: leftPadding },
      maxZoom: 4.5,
      duration: animate ? 850 : 0,
      pitch: 0,
      bearing: 0,
    });
    if (!animate) finishFit();
  }

  function fitState(feature) {
    map.fitBounds(calculateGeometryBounds(feature.geometry), {
      padding: panelPadding(),
      maxZoom: 6.7,
      duration: 950,
      pitch: 0,
      bearing: 0,
    });
  }

  function boundsIntersect(view, target) {
    return view.getEast() > target[0][0]
      && view.getWest() < target[1][0]
      && view.getNorth() > target[0][1]
      && view.getSouth() < target[1][1];
  }

  function getStateFeature(code) {
    return states.features.find((feature) => feature.properties.sigla === code);
  }

  function periodLabel(period) { return demoStore.history.periods.find(item => item.id === period)?.label || period; }
  function filteredLabel() {
    const op = state.operator === "all" ? "Todas as operadoras" : operatorNames[state.operator];
    const project = state.project === "all" ? "Todos os projetos" : (demoStore.projects[state.operator] || demoStore.projects.all || []).find(item => item[0] === state.project)?.[1] || state.project;
    return `${op} / ${project} \u2022 ${["base", "projects"].includes(state.metric) ? "Atual · CMDB real" : `${periodLabel(state.period)} · demonstração`} \u2022 ${modeNames[state.metric]}`;
  }

  function restoreSelectedStateAfterMapLoad() {
    if (!state.selectedUF) return;
    const feature = getStateFeature(state.selectedUF);
    if (!feature) {
      state.selectedUF = null;
      saveMapState();
      return;
    }
    applyOperatorFilter();
    updateStatePanel(state.selectedUF);
    openStatePanel();
    fitState(feature);
  }

  function updateStatePanel(code) {
    const feature = getStateFeature(code);
    const data = demoData[code];
    if (!feature || !data) return;
    const operatorTotals = data.allOperators || data;
    const dominant = dominantOperator(operatorTotals);
    const stateName = feature.properties.nome;
    panel.querySelector("[data-panel-code]").textContent = code;
    panel.querySelector("[data-panel-name]").textContent = stateName;
    const flag = panel.querySelector("[data-panel-flag]");
    if (flag && stateFlags[code]) {
      flag.src = stateFlags[code];
      flag.alt = `Bandeira de ${stateName}`;
    }
    panel.querySelector("[data-panel-total]").textContent = numberFormat.format(metricValue(data));
    const panelNote = panel.querySelector("[data-panel-note]");
    if (panelNote) panelNote.textContent = ["base", "projects"].includes(state.metric)
      ? "Links, projetos e provedores vêm da CMDB real. Chamados, reincidências e motivos são demonstrativos."
      : "Links vêm da CMDB real. Chamados, reincidências e motivos são demonstrativos para validação da experiência.";
    panel.querySelector("[data-panel-scope]").textContent = ["base", "projects"].includes(state.metric)
      ? `${state.metric === "projects" ? "Projeto / cliente" : "Links"} CMDB real \u2022 Atual`
      : `${selectedMetricLabel()} demonstrativos \u2022 ${periodLabel(state.period)}`;
    panel.querySelector("[data-panel-context]").textContent = filteredLabel();
    panel.querySelector("[data-panel-total-small]").textContent = numberFormat.format(data.total_links);
    panel.querySelector("[data-panel-claro]").textContent = numberFormat.format(operatorTotals.claro || 0);
    panel.querySelector("[data-panel-vivo]").textContent = numberFormat.format(operatorTotals.vivo || 0);
    panel.querySelector("[data-panel-algar]").textContent = numberFormat.format(operatorTotals.algar || 0);
    const totalOperators = ["claro", "vivo", "algar"].reduce((sum, key) => sum + (operatorTotals[key] || 0), 0);
    ["claro", "vivo", "algar"].forEach((key) => {
      const meter = panel.querySelector(`[data-panel-meter="${key}"]`);
      if (meter) meter.style.width = `${totalOperators ? Math.round((operatorTotals[key] / totalOperators) * 100) : 0}%`;
    });
    panel.querySelector("[data-panel-calls]").textContent = numberFormat.format(data.chamados);
    panel.querySelector("[data-panel-repeat]").textContent = numberFormat.format(data.reincidentes);
    const callRate = data.total_links ? data.chamados / data.total_links * 100 : 0;
    const repeatRate = data.chamados ? data.reincidentes / data.chamados * 100 : 0;
    panel.querySelector("[data-panel-call-rate]").textContent = `${callRate.toLocaleString("pt-BR", {minimumFractionDigits:1,maximumFractionDigits:1})}`;
    panel.querySelector("[data-panel-repeat-rate]").textContent = `${repeatRate.toLocaleString("pt-BR", {minimumFractionDigits:1,maximumFractionDigits:1})}%`;
    const reasons = Object.entries(data.motivos).sort((a,b)=>b[1]-a[1]).slice(0,5);
    panel.querySelector("[data-panel-reasons]").innerHTML = reasons.length ? reasons.map(([key,value])=>`<div class="panel-reason-row"><span>${motiveNames[key] || "Sem interven\u00e7\u00e3o"}</span><b>${numberFormat.format(value)}</b></div>`).join("") : '<p class="panel-empty">Sem registros para este recorte.</p>';
    const projectList = panel.querySelector("[data-panel-projects]");
    if (projectList) {
      const topProjects = Object.entries(data.projects || {}).sort((a,b)=>b[1]-a[1]).slice(0,5);
      projectList.innerHTML = topProjects.length ? topProjects.map(([name,count])=>`<div class="panel-reason-row"><span>${escapeTooltip(name)}</span><b>${numberFormat.format(count)} links</b></div>`).join("") : '<p class="panel-empty">Sem projetos classificados nesta UF.</p>';
    }
    const providerList = panel.querySelector("[data-panel-providers]");
    if (providerList) {
      const topProviders = Object.entries(data.providers || {}).sort((a,b)=>b[1]-a[1]).slice(0,5);
      providerList.innerHTML = topProviders.length ? topProviders.map(([name,count])=>`<div class="panel-reason-row"><span>${escapeTooltip(name)}</span><b>${numberFormat.format(count)} links</b></div>`).join("") : '<p class="panel-empty">Sem provedores classificados nesta UF.</p>';
    }
    const periods=demoStore.history.periods; const periodIndex=periods.findIndex(item=>item.id===state.period); const previous=periods[periodIndex-1];
    const historyEl=panel.querySelector("[data-panel-history]");
    if(previous){const prior=window.ArionGeoData.aggregate(demoStore,{...state,period:previous.id})[code] || {chamados:0,reincidentes:0}; const delta=prior.chamados ? (data.chamados-prior.chamados)/prior.chamados*100 : null; historyEl.innerHTML=`<div class="panel-history-line"><span>${previous.label}</span><b>${numberFormat.format(prior.chamados)} chamados</b></div><div class="panel-history-line"><span>${periodLabel(state.period)}</span><b>${numberFormat.format(data.chamados)} chamados</b></div><p class="panel-delta">${delta===null?"Sem base comparativa":`${delta>=0?"+":""}${delta.toLocaleString("pt-BR",{maximumFractionDigits:1})}% vs. m\u00eas anterior`}</p>`;} else {historyEl.innerHTML='<p class="panel-empty">Sem m\u00eas anterior para compara\u00e7\u00e3o.</p>'; }
    const dominantElement = panel.querySelector("[data-panel-dominant]");
    dominantElement.lastChild.textContent = operatorNames[dominant] || "Não classificada";
    dominantElement.querySelector("i").className = operatorNames[dominant] ? `operator-swatch operator-swatch--${dominant}` : "";
    document.querySelector("[data-selected-name]").textContent = stateName;
  }

  function openStatePanel() {
    panel.hidden = false;
    panel.inert = false;
    panel.setAttribute("aria-hidden", "false");
    root.classList.add("has-selection");
    document.querySelector(".geo-heading").classList.add("is-selected");
    root.querySelector("[data-panel-backdrop]").classList.add("is-visible");
    breadcrumb.hidden = false;
    if (map) map.resize();
    window.requestAnimationFrame(() => panel.classList.add("is-open"));
  }

  function closeStatePanel() {
    panel.classList.remove("is-open");
    panel.setAttribute("aria-hidden", "true");
    panel.inert = true;
    window.setTimeout(() => {
      if (!state.selectedUF) panel.hidden = true;
    }, 230);
    root.classList.remove("has-selection");
    document.querySelector(".geo-heading").classList.remove("is-selected");
    root.querySelector("[data-panel-backdrop]").classList.remove("is-visible");
    breadcrumb.hidden = true;
    if (map) map.resize();
  }

  function selectState(feature) {
    hideStateTooltip();
    state.selectedUF = feature.properties.sigla;
    saveMapState();
    applyOperatorFilter();
    updateStatePanel(state.selectedUF);
    openStatePanel();
    fitState(feature);
    root.querySelector("[data-map-announcement]").textContent = `${feature.properties.nome}, ${formatNumber(demoData[state.selectedUF].total_links)} links reais do CMDB.`;
  }

  function clearStateSelection() {
    if (!state.selectedUF) return;
    state.selectedUF = null;
    saveMapState();
    closeStatePanel();
    applyOperatorFilter();
    fitBrazil();
    root.querySelector("[data-map-announcement]").textContent = "Visão geral do Brasil.";
  }

  function loadBrazilStates() {
    setLoading(true);
    setMessage("Preparando mapa", "Carregando as unidades federativas.");
    return Promise.all([
      fetch(root.dataset.geojsonUrl).then((response) => {
        if (!response.ok) throw new Error(`GeoJSON HTTP ${response.status}`);
        return response.json();
      }),
      window.ArionGeoData.load({ api: root.dataset.apiUrl, base: root.dataset.baseUrl, history: root.dataset.historyUrl, projects: root.dataset.projectsUrl, reasons: root.dataset.reasonsUrl }),
    ]).then(([geojson, store]) => {
      if (!geojson || geojson.type !== "FeatureCollection" || geojson.features.length !== 27) {
        throw new Error("O GeoJSON deve conter uma FeatureCollection com 27 UFs.");
      }
      const codes = new Set(geojson.features.map((feature) => feature.properties && feature.properties.sigla));
      if (codes.size !== 27) throw new Error("O GeoJSON deve conter 27 siglas distintas.");
      states = geojson;
      stateGeometryBounds = geojson.features.reduce((bounds, feature) => {
        const featureBounds = calculateGeometryBounds(feature.geometry);
        return [
          [Math.min(bounds[0][0], featureBounds[0][0]), Math.min(bounds[0][1], featureBounds[0][1])],
          [Math.max(bounds[1][0], featureBounds[1][0]), Math.max(bounds[1][1], featureBounds[1][1])],
        ];
      }, [[Infinity, Infinity], [-Infinity, -Infinity]]);
      demoStore = store;
      loadMapState();
      populatePeriodAndProject();
      refreshGeoView();
      return geojson;
    });
  }

  function createLabelCollection() {
    return {
      type: "FeatureCollection",
      features: Object.entries(stateLabels).map(([code, coordinates]) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates },
        properties: { sigla: code },
      })),
    };
  }

  function addMapLayers() {
    const palette = currentThemePalette();
    map.addSource(sourceId, { type: "geojson", data: makeDisplayCollection(), promoteId: "sigla" });
    map.addSource("uf-labels", { type: "geojson", data: createLabelCollection() });
    map.addLayer({
      id: fillLayerId,
      type: "fill",
      source: sourceId,
      paint: {
        "fill-color": fillColorExpression(palette),
        "fill-opacity": ["case", ["boolean", ["get", "selecionado"], false], 0.96, ["boolean", ["get", "ha_selecao"], false], 0.38, 0.9],
        "fill-antialias": true,
      },
    });
    map.addLayer({
      id: lineLayerId,
      type: "line",
      source: sourceId,
      paint: {
        "line-color": ["case", ["boolean", ["feature-state", "hover"], false], palette.borderHover, palette.borderColor],
        "line-width": ["case", ["boolean", ["feature-state", "hover"], false], 1.3, 0.65],
      },
    });
    map.addLayer({
      id: selectionLayerId,
      type: "line",
      source: sourceId,
      filter: ["==", ["get", "selecionado"], true],
      paint: { "line-color": palette.selectionColor, "line-width": 2.1 },
    });
    map.addLayer({
      id: labelLayerId,
      type: "symbol",
      source: "uf-labels",
      layout: {
        "text-field": ["get", "sigla"],
        "text-font": ["DIN Offc Pro Medium", "Arial Unicode MS Regular"],
        "text-size": ["interpolate", ["linear"], ["zoom"],
          3, ["match", ["get", "sigla"], "RN", 7, "PB", 7, "PE", 7, "AL", 7, "SE", 7, 9],
          5, ["match", ["get", "sigla"], "RN", 9, "PB", 9, "PE", 9, "AL", 9, "SE", 9, 12],
          7, ["match", ["get", "sigla"], "RN", 11, "PB", 11, "PE", 11, "AL", 11, "SE", 11, 14],
        ],
        "text-letter-spacing": 0.08,
        "text-allow-overlap": true,
        "text-ignore-placement": true,
      },
      paint: {
        "text-color": palette.labelColor,
        "text-opacity": ["case", ["boolean", ["get", "ha_selecao"], false], 0.68, 0.96],
        "text-halo-color": palette.labelHalo,
        "text-halo-width": 1.15,
      },
    });
  }

  function bindMapInteractions() {
    const toolbar = document.querySelector(".geo-toolbar");
    const requiredElements = {
      toolbar,
      motiveSelect: toolbar?.querySelector("[data-motive-filter]"),
      motiveWrap: toolbar?.querySelector("[data-motives-select]"),
      searchInput: toolbar?.querySelector("[data-state-search]"),
      searchList: toolbar?.querySelector("[data-state-search-results]"),
      searchWrap: toolbar?.querySelector(".geo-search-wrap"),
      nationalCollapse: root.querySelector("[data-national-collapse]"),
      nationalExpand: root.querySelector("[data-national-expand]"),
      brazilLink: document.querySelector("[data-brazil-link]"),
      panelClose: root.querySelector("[data-panel-close]"),
      panelBackdrop: root.querySelector("[data-panel-backdrop]"),
      retry: root.querySelector("[data-map-retry]"),
    };
    const missing = Object.entries(requiredElements).filter(([, element]) => !element).map(([name]) => name);
    if (missing.length) throw new Error(`Controles do mapa ausentes: ${missing.join(", ")}`);

    if (!mapInteractionsBound) {
      map.on("mousemove", fillLayerId, showStateTooltip);
      map.on("mouseleave", fillLayerId, () => {
        map.getCanvas().style.cursor = "";
        hideStateTooltip();
      });
      map.on("mouseenter", fillLayerId, () => { map.getCanvas().style.cursor = "pointer"; });
      map.on("click", fillLayerId, (event) => {
        const feature = event.features && event.features[0];
        if (feature) selectState(feature);
      });
      map.on("click", (event) => {
        const feature = map.queryRenderedFeatures(event.point, { layers: [fillLayerId] })[0];
        if (!feature && state.selectedUF) clearStateSelection();
      });
      map.on("moveend", () => {
        const selected = state.selectedUF && getStateFeature(state.selectedUF);
        const target = selected ? calculateGeometryBounds(selected.geometry) : brazilBounds;
        if (!boundsIntersect(map.getBounds(), target)) {
          if (selected) fitState(selected);
          else fitBrazil();
        }
      });
      mapInteractionsBound = true;
    }
    if (uiBound) return;
    const operatorButtons = [...document.querySelectorAll("[data-operator]")];
    const modeButtons = [...document.querySelectorAll("[data-mode]")];
    const { motiveSelect, motiveWrap, searchInput, searchList, searchWrap,
      nationalCollapse, nationalExpand, brazilLink, panelClose, panelBackdrop, retry } = requiredElements;
    const setMode = (mode) => {
      state.metric = mode;
      modeButtons.forEach((button) => {
        const active = button.dataset.mode === mode;
        button.classList.toggle("is-selected", active);
        button.setAttribute("aria-pressed", String(active));
      });
      motiveWrap.hidden = mode !== "motives";
      const periodSelect = document.querySelector("[data-period-filter]");
      periodSelect.disabled = ["base", "projects"].includes(mode);
      [...periodSelect.options].forEach(option => { option.textContent = periodSelect.disabled && option.value === state.period ? "Atual" : (option.dataset.label || option.textContent); });
      refreshGeoView();
    };
    modeButtons.forEach((button) => button.addEventListener("click", () => setMode(button.dataset.mode)));
    motiveSelect.addEventListener("change", () => {
      state.reason = motiveSelect.value;
      refreshGeoView();
    });
    operatorButtons.forEach((button) => {
      button.addEventListener("click", () => {
        if (button.disabled) return;
        state.operator = button.dataset.operator;
        operatorButtons.forEach((item) => {
          const isActive = item === button;
          item.classList.toggle("is-selected", isActive);
          item.setAttribute("aria-pressed", String(isActive));
        });
        state.project = "all";
        updateProjectOptions();
        document.querySelector("[data-project-filter]").value = "all";
        refreshGeoView();
      });
    });
    document.querySelector("[data-project-filter]").addEventListener("change", event => { state.project = event.target.value; refreshGeoView(); });
    document.querySelector("[data-period-filter]").addEventListener("change", event => { state.period = event.target.value; refreshGeoView(); });
    root.querySelectorAll("[data-national-tab]").forEach((tab) => {
      tab.addEventListener("click", () => {
        state.nationalPanelTab = tab.dataset.nationalTab;
        saveMapState();
        renderNationalPanel();
      });
    });
    nationalCollapse.addEventListener("click", () => setNationalCollapsed(true));
    nationalExpand.addEventListener("click", () => setNationalCollapsed(false));
    searchInput.addEventListener("input", () => {
      searchActiveIndex = -1;
      renderSearchResults(searchInput.value);
    });
    searchInput.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown" && !searchList.hidden) {
        event.preventDefault();
        searchActiveIndex = (searchActiveIndex + 1) % searchOptions.length;
        searchList.querySelectorAll("[role=option]").forEach((option, index) => option.setAttribute("aria-selected", String(index === searchActiveIndex)));
        searchInput.setAttribute("aria-activedescendant", `state-option-${searchOptions[searchActiveIndex].properties.sigla}`);
      } else if (event.key === "ArrowUp" && !searchList.hidden) {
        event.preventDefault();
        searchActiveIndex = (searchActiveIndex - 1 + searchOptions.length) % searchOptions.length;
        searchList.querySelectorAll("[role=option]").forEach((option, index) => option.setAttribute("aria-selected", String(index === searchActiveIndex)));
        searchInput.setAttribute("aria-activedescendant", `state-option-${searchOptions[searchActiveIndex].properties.sigla}`);
      } else if (event.key === "Enter" && !searchList.hidden && searchOptions.length) {
        event.preventDefault();
        chooseSearchResult(searchOptions[Math.max(searchActiveIndex, 0)].properties.sigla);
      } else if (event.key === "Escape" && !searchList.hidden) {
        event.stopPropagation();
        closeSearch();
      }
    });
    searchList.addEventListener("click", (event) => {
      const option = event.target.closest("[data-search-code]");
      if (option) chooseSearchResult(option.dataset.searchCode);
    });
    document.addEventListener("click", (event) => {
      if (!searchWrap.contains(event.target)) closeSearch();
    });
    brazilLink.addEventListener("click", clearStateSelection);
    panelClose.addEventListener("click", clearStateSelection);
    panelBackdrop.addEventListener("click", clearStateSelection);
    retry.addEventListener("click", initializeMap);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && state.selectedUF) clearStateSelection();
    });
    window.addEventListener("resize", () => {
      if (!map) return;
      map.resize();
      if (state.selectedUF) {
        const feature = getStateFeature(state.selectedUF);
        if (feature) fitState(feature);
      } else {
        fitBrazil(false);
      }
    });
    uiBound = true;
  }

  window.addEventListener("arion:themechange", (event) => {
    applyMapTheme(event.detail?.theme || document.documentElement.dataset.theme);
  });

  function initializeMap() {
    if (!root.dataset.token) {
      clearError();
      setLoading(false);
      setMessage("Mapbox não configurado", "Adicione MAPBOX_PUBLIC_TOKEN ao arquivo .env para habilitar o mapa.", true);
      return;
    }
    if (!window.mapboxgl) {
      showError("Não foi possível carregar o Mapbox GL JS.");
      return;
    }
    if (map) {
      map.remove();
      map = null;
      mapInteractionsBound = false;
    }
    if (popup) popup.remove();
    popup = null;
    tooltipContent = null;
    hoveredCode = null;
    mapLoaded = false;
    clearError();
    if (state.selectedUF) closeStatePanel();
    panel.hidden = true;
    panel.inert = true;
    setLoading(true);
    setMessage("Preparando mapa", "Carregando as unidades federativas.");

    loadBrazilStates().then(() => {
      const palette = currentThemePalette();
      mapboxgl.accessToken = root.dataset.token;
      map = new mapboxgl.Map({
        container: mapElement,
        style: {
          version: 8,
          glyphs: "mapbox://fonts/mapbox/{fontstack}/{range}.pbf",
          sources: {},
          layers: [{ id: "fundo-arion", type: "background", paint: { "background-color": palette.background } }],
        },
        bounds: brazilBounds,
        fitBoundsOptions: { padding: { top: 34, right: 42, bottom: 38, left: 42 }, maxZoom: 4.35 },
        maxBounds: [[-120, -54], [8, 26]],
        minZoom: 2.5,
        maxZoom: 8,
        minPitch: 0,
        maxPitch: 0,
        pitch: 0,
        bearing: 0,
        touchPitch: false,
        attributionControl: true,
        renderWorldCopies: false,
        logoPosition: "bottom-left",
        cooperativeGestures: false,
      });
      map.addControl(new mapboxgl.NavigationControl({ showCompass: false, visualizePitch: false }), "top-right");
      map.dragRotate.disable();
      map.touchZoomRotate.disableRotation();
      map.on("load", () => {
        try {
          addMapLayers();
          mapLoaded = true;
        } catch (error) {
          console.error("Falha ao montar as camadas geográficas do mapa:", error);
          showError("As camadas geográficas não puderam ser inicializadas.");
          return;
        }
        try {
          bindMapInteractions();
        } catch (error) {
          console.error("Falha ao vincular os controles do mapa:", error);
          const announcement = root.querySelector("[data-map-announcement]");
          if (announcement) announcement.textContent = "Não foi possível inicializar os controles do mapa.";
        }
        try {
          applyMapTheme(document.documentElement.dataset.theme || "dark");
          renderNationalPanel();
          map.resize();
          fitBrazil(false);
          restoreSelectedStateAfterMapLoad();
          const loadingFallback = window.setTimeout(() => {
            if (mapLoaded && map) {
              setLoading(false);
              hideMessage();
            }
          }, 8000);
          map.once("idle", () => {
            window.clearTimeout(loadingFallback);
            setLoading(false);
            hideMessage();
          });
        } catch (error) {
          console.error("Falha ao atualizar a apresentação do mapa:", error);
        }
      });
      map.on("error", (event) => {
        const error = event && event.error;
        if (error && error.name === "AbortError") return;
        if (!mapLoaded) {
          console.error("Falha ao inicializar Mapbox GL JS:", error || event);
          showError("Verifique o token público e a conexão com o Mapbox.");
        }
      });
    }).catch((error) => {
      console.error("Falha ao carregar GeoJSON ou dados demonstrativos:", error);
      showError("Não foi possível carregar o arquivo local das unidades federativas.");
    });
  }

  initializeMap();
})();
