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
  const modeNames = { base: "links", calls: "chamados", repeat: "reincidentes", motives: "ocorrências" };
  const motiveNames = { falha_massiva: "Falha massiva", rompimento_fibra: "Rompimento de fibra", troca_drop: "Troca de drop", equipamento: "Equipamento", cabo_desconectado: "Cabo desconectado", falha_eletrica: "Falha elétrica", outros: "Outros" };
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
  let demoData = null;
  let activeOperator = "all";
  let activeMode = "base";
  let activeMotive = "all";
  let nationalTab = "summary";
  let nationalCollapsed = false;
  let searchOptions = [];
  let searchActiveIndex = -1;
  let selectedCode = null;
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
    return ["claro", "vivo", "algar"].reduce((current, operator) => (
      data[operator] > data[current] ? operator : current
    ), "claro");
  }

  function metricValue(data) {
    if (activeMode === "calls") return data.chamados;
    if (activeMode === "repeat") return data.reincidentes;
    if (activeMode === "motives") return activeMotive === "all"
      ? Object.values(data.motivos || {}).reduce((sum, value) => sum + value, 0)
      : (data.motivos?.[activeMotive] || 0);
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
        const activeCount = activeOperator === "all" ? metrics.total_links : metrics[activeOperator];
        const intensity = activeMode === "base"
          ? activeOperator === "all" ? 1 : Math.sqrt(activeCount / totals[activeOperator])
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
            selecionado: code === selectedCode,
            ha_selecao: Boolean(selectedCode),
          },
        };
      }),
    };
  }

  function colorExpression(palette = currentThemePalette()) {
    const ops = palette.operators;
    if (activeMode !== "base") {
      const scale = palette.metrics[activeMode];
      return ["interpolate", ["linear"], ["get", "intensidade"], 0, scale.low, 0.45, scale.mid, 1, scale.high];
    }
    if (activeOperator === "all") {
      return ["match", ["get", "dominante"],
        "claro", ops.claro.base,
        "vivo", ops.vivo.base,
        "algar", ops.algar.base,
        palette.defaultFill];
    }
    const scale = ops[activeOperator];
    return ["interpolate", ["linear"], ["get", "intensidade"], 0, scale.low, 0.35, scale.mid, 1, scale.high];
  }

  function fillColorExpression(palette = currentThemePalette()) {
    return [
      "case",
      ["boolean", ["feature-state", "hover"], false], palette.hoverFill,
      colorExpression(palette),
    ];
  }

  function applyOperatorFilter() {
    if (!map || !map.getSource(sourceId) || !demoData || !states) return;
    if (hoveredCode) map.setFeatureState({ source: sourceId, id: hoveredCode }, { hover: false });
    if (popup) popup.remove();
    hoveredCode = null;
    const palette = currentThemePalette();
    map.getSource(sourceId).setData(makeDisplayCollection());
    map.setPaintProperty(fillLayerId, "fill-color", fillColorExpression(palette));
    map.setPaintProperty(fillLayerId, "fill-opacity", [
      "case",
      ["boolean", ["get", "selecionado"], false], 0.96,
      ["boolean", ["get", "ha_selecao"], false], 0.38,
      0.9,
    ]);
    updateLegend();
    if (selectedCode) updateStatePanel(selectedCode);
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
    if (activeMode !== "base") {
      legend.classList.add("geo-legend--scale");
      legend.innerHTML = `<span class="legend-scale-label">Menos ${modeNames[activeMode]}</span><span class="legend-scale legend-scale--${activeMode}"></span><span class="legend-scale-label">Mais</span>`;
      return;
    }
    if (activeOperator === "all") {
      legend.classList.remove("geo-legend--scale");
      legend.innerHTML = '<span class="legend-item"><i class="legend-dot legend-dot--claro"></i>Claro</span><span class="legend-item"><i class="legend-dot legend-dot--vivo"></i>Vivo</span><span class="legend-item"><i class="legend-dot legend-dot--algar"></i>Algar</span>';
      return;
    }
    legend.classList.add("geo-legend--scale");
    legend.innerHTML = `<span class="legend-scale-label">Baixa intensidade</span><span class="legend-scale" data-scale="${activeOperator}"></span><span class="legend-scale-label">Alta</span><span class="legend-operator">${operatorNames[activeOperator]}</span>`;
  }

  function totalsByField(field) {
    return Object.values(demoData || {}).reduce((sum, row) => sum + (row[field] || 0), 0);
  }

  function selectedMetricLabel() {
    if (activeMode === "calls") return "Chamados";
    if (activeMode === "repeat") return "Reincidentes";
    if (activeMode === "motives") return activeMotive === "all" ? "Ocorrencias" : motiveNames[activeMotive];
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
      states: states.features.length,
    };
    view.setAttribute("aria-labelledby", `national-tab-${nationalTab}`);
    document.querySelectorAll("[data-national-tab]").forEach((tab) => {
      tab.setAttribute("aria-selected", String(tab.dataset.nationalTab === nationalTab));
      tab.tabIndex = tab.dataset.nationalTab === nationalTab ? 0 : -1;
    });

    if (nationalTab === "summary") {
      view.innerHTML = `<div class="national-kpis"><div><strong>${numberFormat.format(totals.links)}</strong><span>Links</span></div><div><strong>${numberFormat.format(totals.calls)}</strong><span>Chamados</span></div><div><strong>${numberFormat.format(totals.repeat)}</strong><span>Reincidentes</span></div><div><strong>${totals.states}</strong><span>UFs</span></div></div><div class="national-leaders"><div><span>Maior base</span><strong>${byLinks[0].name}</strong><small>${numberFormat.format(demoData[byLinks[0].code].total_links)} links</small></div><div><span>Mais chamados</span><strong>${byCalls[0].name}</strong><small>${numberFormat.format(demoData[byCalls[0].code].chamados)} chamados</small></div></div>`;
      return;
    }

    if (nationalTab === "ranking") {
      const label = selectedMetricLabel();
      const rows = [...stateRows].sort((a, b) => b.value - a.value).slice(0, 5);
      view.innerHTML = `<div class="national-view-heading"><span>Top 5 por ${label.toLowerCase()}</span><span class="demo-inline">Demo</span></div><ol class="national-ranking">${rows.map((row, index) => `<li><span class="national-rank-number">${String(index + 1).padStart(2, "0")}</span><img src="${stateFlags[row.code] || ""}" alt="" width="22" height="15" loading="lazy"><span class="national-rank-name">${row.name}</span><strong>${numberFormat.format(row.value)}</strong></li>`).join("")}</ol>`;
      return;
    }

    const operators = [
      { name: "Claro", key: "claro", value: totalsByField("claro") },
      { name: "Vivo", key: "vivo", value: totalsByField("vivo") },
      { name: "Algar", key: "algar", value: totalsByField("algar") },
    ];
    view.innerHTML = `<div class="national-view-heading"><span>Participacao na base</span><span class="demo-inline">Dados demonstrativos</span></div><div class="national-distribution">${operators.map((item) => `<div class="national-distribution-row"><span><i class="operator-swatch operator-swatch--${item.key}"></i>${item.name}</span><strong>${(item.value / totals.links * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%</strong><small>${numberFormat.format(item.value)}</small><i class="national-distribution-track"><b class="operator-fill--${item.key}" data-value="${item.value}" data-max="${totals.links}"></b></i></div>`).join("")}</div>`;
    view.querySelectorAll("[data-value][data-max]").forEach((bar) => {
      bar.style.width = `${Math.max(0, Number(bar.dataset.value) / Number(bar.dataset.max) * 100)}%`;
    });
  }

  function setNationalCollapsed(collapsed) {
    const national = root.querySelector("[data-national-panel]");
    const collapse = root.querySelector("[data-national-collapse]");
    const expand = root.querySelector("[data-national-expand]");
    const content = root.querySelector("[data-national-content]");
    nationalCollapsed = collapsed;
    national.classList.toggle("is-collapsed", collapsed);
    national.setAttribute("aria-hidden", String(collapsed));
    national.inert = collapsed;
    collapse.setAttribute("aria-expanded", String(!collapsed));
    collapse.setAttribute("aria-label", collapsed ? "Expandir resumo nacional" : "Recolher resumo nacional");
    content.setAttribute("aria-hidden", String(collapsed));
    content.inert = collapsed;
    expand.hidden = !collapsed;
  }

  function normalizeSearch(value) {
    return value.trim().normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("pt-BR");
  }

  function closeSearch() {
    const input = root.querySelector("[data-state-search]");
    const list = root.querySelector("[data-state-search-results]");
    list.hidden = true;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
    searchActiveIndex = -1;
  }

  function renderSearchResults(query) {
    const list = root.querySelector("[data-state-search-results]");
    const input = root.querySelector("[data-state-search]");
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
    root.querySelector("[data-state-search]").value = `${feature.properties.sigla} - ${feature.properties.nome}`;
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

  function createTooltip() {
    const element = document.createElement("section");
    element.className = "state-tooltip";
    element.setAttribute("aria-label", "Resumo demonstrativo da unidade federativa");
    element.innerHTML = [
      '<div class="tooltip-heading"><div><span data-tooltip-code></span><strong data-tooltip-name></strong></div><span class="tooltip-total"><b data-tooltip-total></b><small>links</small></span></div>',
      '<div class="tooltip-primary-metric"><strong data-tooltip-primary></strong><span data-tooltip-primary-label></span></div>',
      '<div class="tooltip-secondary-metrics"><span>Chamados <b data-tooltip-calls></b></span><span>Reincidentes <b data-tooltip-repeat></b></span></div>',
      '<div class="tooltip-rate" data-tooltip-rate></div>',
      '<div class="tooltip-operators"><div><i class="operator-swatch operator-swatch--claro"></i>Claro<strong data-tooltip-claro></strong></div>',
      '<div><i class="operator-swatch operator-swatch--vivo"></i>Vivo<strong data-tooltip-vivo></strong></div>',
      '<div><i class="operator-swatch operator-swatch--algar"></i>Algar<strong data-tooltip-algar></strong></div></div>',
      '<div class="tooltip-dominant"><span>Operadora predominante</span><strong data-tooltip-dominant></strong></div>',
    ].join("");
    return element;
  }

  function updateTooltip(feature) {
    const code = feature.properties.sigla;
    const data = demoData[code];
    if (!tooltipContent) tooltipContent = createTooltip();
    const setText = (selector, value) => {
      const target = tooltipContent.querySelector(selector);
      if (target) target.textContent = value;
    };
    setText("[data-tooltip-code]", code);
    setText("[data-tooltip-name]", feature.properties.nome);
    setText("[data-tooltip-total]", numberFormat.format(data.total_links));
    setText("[data-tooltip-claro]", numberFormat.format(data.claro));
    setText("[data-tooltip-vivo]", numberFormat.format(data.vivo));
    setText("[data-tooltip-algar]", numberFormat.format(data.algar));
    setText("[data-tooltip-dominant]", operatorNames[dominantOperator(data)]);
    setText("[data-tooltip-calls]", numberFormat.format(data.chamados));
    setText("[data-tooltip-repeat]", numberFormat.format(data.reincidentes));
    const primary = activeMode === "base" ? (activeOperator === "all" ? data.total_links : data[activeOperator]) : metricValue(data);
    const primaryLabel = activeMode === "base"
      ? (activeOperator === "all" ? "links" : `links ${operatorNames[activeOperator]}`)
      : (activeMode === "motives" && activeMotive !== "all" ? motiveNames[activeMotive] : modeNames[activeMode]);
    setText("[data-tooltip-primary]", numberFormat.format(primary));
    setText("[data-tooltip-primary-label]", primaryLabel);
    const rate = data.chamados ? Math.round((data.reincidentes / data.chamados) * 100) : 0;
    setText("[data-tooltip-rate]", `Taxa de reincidencia ${rate}%`);
    tooltipContent.classList.toggle("tooltip-is-base", activeMode === "base");
    const rateLine = tooltipContent.querySelector("[data-tooltip-rate]");
    if (rateLine) rateLine.hidden = activeMode !== "repeat";
    const operators = tooltipContent.querySelector(".tooltip-operators");
    if (operators) operators.hidden = activeMode !== "base";
  }

  function showStateTooltip(event) {
    const feature = event.features && event.features[0];
    if (!feature) return;
    const code = feature.properties.sigla;
    if (code !== hoveredCode) {
      setFeatureHover(code);
      updateTooltip(feature);
      if (!popup) {
        popup = new mapboxgl.Popup({ closeButton: false, closeOnClick: false, offset: 13, maxWidth: "none", className: "geo-popup" });
        popup.setLngLat(event.lngLat).setDOMContent(tooltipContent).addTo(map);
      }
    }
    if (popup) popup.setLngLat(event.lngLat);
  }

  function hideStateTooltip() {
    if (hoveredCode) setFeatureHover(null);
    if (popup) popup.remove();
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
    map.fitBounds(brazilBounds, {
      padding: { top: 36, right: 44, bottom: 40, left: 44 },
      maxZoom: 4.35,
      duration: animate ? 850 : 0,
      pitch: 0,
      bearing: 0,
    });
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

  function updateStatePanel(code) {
    const feature = getStateFeature(code);
    const data = demoData[code];
    if (!feature || !data) return;
    const dominant = dominantOperator(data);
    const stateName = feature.properties.nome;
    panel.querySelector("[data-panel-code]").textContent = code;
    panel.querySelector("[data-panel-name]").textContent = stateName;
    const flag = panel.querySelector("[data-panel-flag]");
    if (flag && stateFlags[code]) {
      flag.src = stateFlags[code];
      flag.alt = `Bandeira de ${stateName}`;
    }
    panel.querySelector("[data-panel-total]").textContent = numberFormat.format(data.total_links);
    panel.querySelector("[data-panel-total-small]").textContent = numberFormat.format(data.total_links);
    panel.querySelector("[data-panel-claro]").textContent = numberFormat.format(data.claro);
    panel.querySelector("[data-panel-vivo]").textContent = numberFormat.format(data.vivo);
    panel.querySelector("[data-panel-algar]").textContent = numberFormat.format(data.algar);
    ["claro", "vivo", "algar"].forEach((key) => {
      const meter = panel.querySelector(`[data-panel-meter="${key}"]`);
      if (meter) meter.style.width = `${data.total_links ? Math.round((data[key] / data.total_links) * 100) : 0}%`;
    });
    panel.querySelector("[data-panel-calls]").textContent = numberFormat.format(data.chamados);
    panel.querySelector("[data-panel-repeat]").textContent = numberFormat.format(data.reincidentes);
    const dominantElement = panel.querySelector("[data-panel-dominant]");
    dominantElement.lastChild.textContent = operatorNames[dominant];
    dominantElement.querySelector("i").className = `operator-swatch operator-swatch--${dominant}`;
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
    window.requestAnimationFrame(() => panel.classList.add("is-open"));
  }

  function closeStatePanel() {
    panel.classList.remove("is-open");
    panel.setAttribute("aria-hidden", "true");
    panel.inert = true;
    window.setTimeout(() => {
      if (!selectedCode) panel.hidden = true;
    }, 230);
    root.classList.remove("has-selection");
    document.querySelector(".geo-heading").classList.remove("is-selected");
    root.querySelector("[data-panel-backdrop]").classList.remove("is-visible");
    breadcrumb.hidden = true;
  }

  function selectState(feature) {
    hideStateTooltip();
    selectedCode = feature.properties.sigla;
    applyOperatorFilter();
    updateStatePanel(selectedCode);
    openStatePanel();
    fitState(feature);
    root.querySelector("[data-map-announcement]").textContent = `${feature.properties.nome}, ${demoData[selectedCode].total_links} links demonstrativos.`;
  }

  function clearStateSelection() {
    if (!selectedCode) return;
    selectedCode = null;
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
      fetch(root.dataset.demoUrl).then((response) => {
        if (!response.ok) throw new Error(`Dados demonstrativos HTTP ${response.status}`);
        return response.json();
      }),
    ]).then(([geojson, data]) => {
      if (!geojson || geojson.type !== "FeatureCollection" || geojson.features.length !== 27) {
        throw new Error("O GeoJSON deve conter uma FeatureCollection com 27 UFs.");
      }
      const codes = new Set(geojson.features.map((feature) => feature.properties && feature.properties.sigla));
      if (codes.size !== 27 || geojson.features.some((feature) => !data[feature.properties.sigla])) {
        throw new Error("As siglas do GeoJSON não correspondem aos dados demonstrativos.");
      }
      states = geojson;
      demoData = data;
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
      if (!feature && selectedCode) clearStateSelection();
    });
    map.on("moveend", () => {
      const selected = selectedCode && getStateFeature(selectedCode);
      const target = selected ? calculateGeometryBounds(selected.geometry) : brazilBounds;
      if (!boundsIntersect(map.getBounds(), target)) {
        if (selected) fitState(selected);
        else fitBrazil();
      }
    });
    if (uiBound) return;
    const operatorButtons = [...document.querySelectorAll("[data-operator]")];
    const modeButtons = [...document.querySelectorAll("[data-mode]")];
    const { motiveSelect, motiveWrap, searchInput, searchList, searchWrap,
      nationalCollapse, nationalExpand, brazilLink, panelClose, panelBackdrop, retry } = requiredElements;
    const setMode = (mode) => {
      activeMode = mode;
      modeButtons.forEach((button) => {
        const active = button.dataset.mode === mode;
        button.classList.toggle("is-selected", active);
        button.setAttribute("aria-pressed", String(active));
      });
      motiveWrap.hidden = mode !== "motives";
      operatorButtons.forEach((button) => {
        button.disabled = mode !== "base";
        button.title = mode === "base" ? "" : "O filtro de operadora se aplica ao modo Base.";
      });
      hideStateTooltip();
      applyOperatorFilter();
      renderNationalPanel();
    };
    modeButtons.forEach((button) => button.addEventListener("click", () => setMode(button.dataset.mode)));
    motiveSelect.addEventListener("change", () => {
      activeMotive = motiveSelect.value;
      hideStateTooltip();
      applyOperatorFilter();
    });
    operatorButtons.forEach((button) => {
      button.addEventListener("click", () => {
        if (button.disabled) return;
        activeOperator = button.dataset.operator;
        operatorButtons.forEach((item) => {
          const isActive = item === button;
          item.classList.toggle("is-selected", isActive);
          item.setAttribute("aria-pressed", String(isActive));
        });
        hideStateTooltip();
        applyOperatorFilter();
      });
    });
    root.querySelectorAll("[data-national-tab]").forEach((tab) => {
      tab.addEventListener("click", () => {
        nationalTab = tab.dataset.nationalTab;
        renderNationalPanel();
      });
    });
    nationalCollapse.addEventListener("click", () => setNationalCollapsed(true));
    nationalExpand.addEventListener("click", () => setNationalCollapsed(false));
    setNationalCollapsed(window.matchMedia("(max-width: 1024px)").matches);
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
      if (event.key === "Escape" && selectedCode) clearStateSelection();
    });
    window.addEventListener("resize", () => {
      if (!map) return;
      map.resize();
      if (selectedCode) {
        const feature = getStateFeature(selectedCode);
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
    }
    if (popup) popup.remove();
    popup = null;
    hoveredCode = null;
    mapLoaded = false;
    clearError();
    if (selectedCode) closeStatePanel();
    panel.hidden = true;
    panel.inert = true;
    selectedCode = null;
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
        maxBounds: [[-104, -42], [-4, 14]],
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
