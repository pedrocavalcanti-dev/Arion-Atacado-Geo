(() => {
  const root = document.querySelector("[data-cmdb-map]");
  if (!root) return;
  const number = new Intl.NumberFormat("pt-BR");
  const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
  const mapElement = document.getElementById("brazil-map");
  const message = root.querySelector("[data-cmdb-message]");
  const errorBox = root.querySelector("[data-cmdb-error]");
  const statePanel = root.querySelector("[data-cmdb-state-panel]");
  const operatorFilter = document.querySelector("[data-cmdb-operator]");
  const projectFilter = document.querySelector("[data-cmdb-project]");
  // Keep the map usable if an older cached template has not received newer controls yet.
  const metricFilter = root.querySelector("[data-cmdb-metric]") || { value: "base", addEventListener() {} };
  const periodFilter = root.querySelector("[data-cmdb-period]") || { value: "current", disabled: true, options: [], selectedOptions: [], querySelector: () => null, addEventListener() {} };
  const reasonFilter = root.querySelector("[data-cmdb-reason]") || { value: "Falha massiva", addEventListener() {} };
  const reasonWrap = root.querySelector("[data-cmdb-reason-wrap]") || { hidden: true };
  const stateSearch = root.querySelector("[data-cmdb-state-search]") || { value: "", addEventListener() {}, setCustomValidity() {}, reportValidity() {} };
  const errorDetail = root.querySelector("[data-cmdb-error-detail]");
  // KPI and note live in the page header, outside the map stage.
  const totalElement = document.querySelector("[data-cmdb-total]");
  const ufNote = document.querySelector("[data-cmdb-uf-note]");
  const stateList = root.querySelector("[data-cmdb-state-list]");
  const stateName = root.querySelector("[data-cmdb-state-name]");
  const stateTotal = root.querySelector("[data-cmdb-state-total]");
  const stateOperators = root.querySelector("[data-cmdb-state-operators]");
  const stateProjects = root.querySelector("[data-cmdb-state-projects]");
  const sourceNote = document.querySelector("[data-cmdb-source-note]");
  const totalLabel = document.querySelector("[data-cmdb-total-label]");
  const stateMetricLabel = root.querySelector("[data-cmdb-state-metric-label]");
  const stateContext = root.querySelector("[data-cmdb-state-context]");
  const required = [mapElement, message, errorBox, statePanel, operatorFilter, projectFilter,
    metricFilter, periodFilter, reasonFilter, reasonWrap, stateSearch,
    totalElement, ufNote,
    stateList, errorDetail, stateName, stateTotal, stateOperators, stateProjects,
    root.querySelector("[data-cmdb-panel-close]"), root.querySelector("[data-cmdb-retry]")];
  const ufNames = { AC:"Acre",AL:"Alagoas",AM:"Amazonas",AP:"Amapá",BA:"Bahia",CE:"Ceará",DF:"Distrito Federal",ES:"Espírito Santo",GO:"Goiás",MA:"Maranhão",MG:"Minas Gerais",MS:"Mato Grosso do Sul",MT:"Mato Grosso",PA:"Pará",PB:"Paraíba",PE:"Pernambuco",PI:"Piauí",PR:"Paraná",RJ:"Rio de Janeiro",RN:"Rio Grande do Norte",RO:"Rondônia",RR:"Roraima",RS:"Rio Grande do Sul",SC:"Santa Catarina",SE:"Sergipe",SP:"São Paulo",TO:"Tocantins" };
  let map;
  let mapLoaded = false;
  let loadingTimer;
  let geojson;
  let aggregate = {};
  let viewData = {};
  let selectedCode = "";
  const reasonNames = ["Falha massiva", "Rompimento de fibra", "Troca de drop", "Equipamento", "Falha elétrica", "Sem intervenção", "Outros"];
  try {
    const saved = JSON.parse(localStorage.getItem("arion-cmdb-map-state") || "{}");
    if (["base", "tickets", "recurrences", "reasons"].includes(saved.metric)) metricFilter.value = saved.metric;
    if ([...periodFilter.options].some(option => option.value === saved.period)) periodFilter.value = saved.period;
  } catch (_error) { /* Ignore a blocked or malformed local preference. */ }
  function stableValue(uf, period, salt) {
    let hash = 0;
    for (const char of `${uf}-${period}-${salt}`) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
    return hash / 4294967295;
  }
  function demoMetrics(uf, links) {
    const period = periodFilter.value === "current" ? "2026-10" : periodFilter.value;
    const rate = .075 + stableValue(uf, period, "ticket-rate") * .085;
    const tickets = links ? Math.max(1, Math.round(links * rate)) : 0;
    const recurrences = Math.min(tickets, Math.round(tickets * (.16 + stableValue(uf, period, "repeat-rate") * .22)));
    const weights = [26, 20, 15, 12, 10, 9, 8].map((weight, index) => weight + Math.round(stableValue(uf, period, `reason-${index}`) * 4));
    const totalWeight = weights.reduce((sum, weight) => sum + weight, 0);
    const reasons = Object.fromEntries(reasonNames.map((name, index) => [name, Math.floor(tickets * weights[index] / totalWeight)]));
    let remainder = tickets - Object.values(reasons).reduce((sum, value) => sum + value, 0);
    for (let index = 0; remainder > 0; index = (index + 1) % reasonNames.length, remainder--) reasons[reasonNames[index]]++;
    return { tickets, recurrences, reasons };
  }
  function valueFor(uf, row) {
    const demo = demoMetrics(uf, row.total_links);
    if (metricFilter.value === "tickets") return demo.tickets;
    if (metricFilter.value === "recurrences") return demo.recurrences;
    if (metricFilter.value === "reasons") return demo.reasons[reasonFilter.value] || 0;
    return row.total_links;
  }
  function metricLabel() { return ({ base: "links CMDB real", tickets: "chamados · demonstração", recurrences: "reincidências · demonstração", reasons: "chamados por motivo · demonstração" })[metricFilter.value]; }
  function refreshMapView() {
    const metric = metricFilter.value;
    const period = periodFilter.value;
    const demo = metric !== "base";
    periodFilter.disabled = !demo;
    reasonWrap.hidden = metric !== "reasons";
    const currentOption = periodFilter.querySelector('option[value="current"]');
    if (currentOption) currentOption.textContent = demo ? "Selecione" : "Atual";
    if (demo && period === "current") periodFilter.value = "2026-10";
    try { localStorage.setItem("arion-cmdb-map-state", JSON.stringify({ metric, period: periodFilter.value })); } catch (_error) { /* Map use does not depend on storage. */ }
    const month = periodFilter.value;
    const monthLabel = periodFilter.selectedOptions[0]?.textContent || "Out/26";
    if (sourceNote) sourceNote.textContent = demo ? `${metric === "tickets" ? "Chamados" : metric === "recurrences" ? "Reincidência" : "Motivos"} · DEMONSTRAÇÃO · ${monthLabel}. Links e filtros vêm da Base CMDB real.` : "Base · CMDB real · snapshot atual.";
    if (totalLabel) totalLabel.textContent = demo ? metricLabel() : "links CMDB";
    updateMap(viewData);
    if (selectedCode) selectState(selectedCode);
  }

  function showError(text) {
    if (message) message.hidden = true;
    if (errorBox) errorBox.hidden = false;
    if (errorDetail) errorDetail.textContent = text;
    if (errorBox && !errorDetail) errorBox.setAttribute("aria-label", text);
  }
  function fillExpression(maximum) {
    const light = document.documentElement.dataset.theme === "light";
    return ["interpolate", ["linear"], ["get", "links"], 0, light ? "#e3e7e3" : "#181b1a", Math.max(1, maximum * .45), light ? "#9aa89d" : "#45554a", Math.max(2, maximum), light ? "#3f7650" : "#92b39b"];
  }
  function updateMap(data) {
    aggregate = data.states || {};
    const features = geojson.features.map(feature => ({
      ...feature,
      properties: { ...feature.properties, links: valueFor(feature.properties.sigla, aggregate[feature.properties.sigla] || { total_links: 0 }) },
    }));
    const max = Math.max(1, ...features.map(feature => feature.properties.links));
    if (map?.getSource("cmdb-states")) map.getSource("cmdb-states").setData({ type: "FeatureCollection", features });
    if (map?.getLayer("cmdb-fill")) map.setPaintProperty("cmdb-fill", "fill-color", fillExpression(max));
    totalElement.textContent = number.format(metricFilter.value === "base" ? data.source_total || 0 : Object.entries(aggregate).reduce((sum, [uf, row]) => sum + valueFor(uf, row), 0));
    const filteredTotal = data.filtered_source_total ?? data.source_total ?? 0;
    ufNote.textContent = `${number.format(filteredTotal - (data.invalid_uf_count || 0))} links com UF válida no recorte; ${number.format(data.invalid_uf_count || 0)} sem UF válida. O total geral CMDB é ${number.format(data.source_total || 0)}.`;
    const ranked = Object.entries(aggregate).sort((a,b) => b[1].total_links - a[1].total_links);
    const displayRanked = ranked.map(([uf, row]) => [uf, { ...row, value: valueFor(uf, row) }]).sort((a,b) => b[1].value-a[1].value);
    stateList.innerHTML = displayRanked.slice(0, 10).map(([uf, row], index) => `<div class="cmdb-state-rank"><span>${String(index + 1).padStart(2,"0")}</span><b>${ufNames[uf] || uf}</b><small>${uf}</small><strong>${number.format(row.value)}</strong><i><em style="width:${row.value / max * 100}%"></em></i></div>`).join("") || '<p>Nenhum link com UF válida.</p>';
  }
  function fillFilters(data) {
    operatorFilter.innerHTML = '<option value="">Todas</option>' + data.operators.map(item => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)}</option>`).join("");
    projectFilter.innerHTML = '<option value="">Todos</option>' + data.projects.map(item => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)}</option>`).join("");
  }
  async function refresh() {
    const url = new URL(root.dataset.apiUrl, window.location.origin);
    if (operatorFilter.value) url.searchParams.set("operator", operatorFilter.value);
    if (projectFilter.value) url.searchParams.set("project", projectFilter.value);
    const response = await fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" }, signal: AbortSignal.timeout(15000) });
    if (!response.ok) throw new Error(`A API da base respondeu HTTP ${response.status}.`);
    const data = await response.json();
    if (!Array.isArray(data.operators) || !Array.isArray(data.projects) || !data.states) {
      throw new Error("A API da base retornou um formato inesperado para o mapa.");
    }
    fillFilters(data);
    operatorFilter.value = url.searchParams.get("operator") || "";
    projectFilter.value = url.searchParams.get("project") || "";
    viewData = data;
    refreshMapView();
  }
  function selectState(code) {
    selectedCode = code;
    const row = aggregate[code] || { total_links: 0, operator_counts: {}, project_counts: {} };
    root.classList.add("has-selection");
    statePanel.hidden = false;
    stateName.textContent = `${ufNames[code] || code} · ${code}`;
    stateTotal.textContent = number.format(valueFor(code, row));
    const demo = demoMetrics(code, row.total_links);
    const isDemo = metricFilter.value !== "base";
    if (stateMetricLabel) stateMetricLabel.textContent = metricLabel();
    if (stateContext) stateContext.textContent = isDemo ? `${number.format(demo.tickets)} chamados demonstrativos · ${number.format(row.total_links)} links reais · ${number.format(demo.recurrences)} reincidências demonstrativas${metricFilter.value === "reasons" ? ` · motivo principal: ${Object.entries(demo.reasons).sort((a,b)=>b[1]-a[1])[0]?.[0] || "—"}` : ""}` : "Contagem real de links presentes no último export CMDB.";
    const countsHtml = (counts, empty) => Object.entries(counts || {}).sort((a,b) => b[1] - a[1]).map(([name, count]) => `<div class="operator-row"><span>${escapeHtml(name)}</span><strong>${number.format(count)}</strong><i class="operator-meter"><b style="width:${row.total_links ? count / row.total_links * 100 : 0}%"></b></i></div>`).join("") || `<p class="value-muted">${empty}</p>`;
    stateOperators.innerHTML = countsHtml(row.operator_counts, "Operadora não classificada.");
    stateProjects.innerHTML = countsHtml(row.project_counts, "Projeto não classificado.");
  }
  function searchState() {
    const query = stateSearch.value.trim().toLocaleUpperCase("pt-BR");
    if (!query) return;
    const code = Object.keys(ufNames).find(uf => uf === query || ufNames[uf].toLocaleUpperCase("pt-BR") === query);
    const feature = code && geojson.features.find(item => item.properties.sigla === code);
    if (!feature) { stateSearch.setCustomValidity("Informe a sigla ou o nome de uma UF."); stateSearch.reportValidity(); return; }
    stateSearch.setCustomValidity("");
    selectState(code);
    if (map && mapLoaded) {
      const points = [];
      const visit = value => Array.isArray(value) && (typeof value[0] === "number" ? points.push(value) : value.forEach(visit));
      visit(feature.geometry.coordinates);
      if (points.length) {
        const bounds = points.reduce((box, point) => box.extend(point), new window.mapboxgl.LngLatBounds(points[0], points[0]));
        map.fitBounds(bounds, { padding: 70, maxZoom: 5.5, duration: 700 });
      }
    }
  }
  async function initialize() {
    window.clearTimeout(loadingTimer);
    mapLoaded = false;
    if (required.some(element => !element)) {
      showError("O template do mapa está sem um elemento obrigatório. Recarregue a página e verifique os atributos data-cmdb-* do painel.");
      return;
    }
    if (!root.dataset.token) return showError("Adicione MAPBOX_PUBLIC_TOKEN ao arquivo .env para habilitar o mapa.");
    if (!window.mapboxgl) return showError("Não foi possível carregar o Mapbox GL JS.");
    try {
      const [geoResponse] = await Promise.all([fetch(root.dataset.geojsonUrl, { signal: AbortSignal.timeout(15000) })]);
      if (!geoResponse.ok) throw new Error("Não foi possível carregar as geometrias estaduais.");
      geojson = await geoResponse.json();
      await refresh();
      window.mapboxgl.accessToken = root.dataset.token;
      map = new window.mapboxgl.Map({
        container: mapElement,
        style: { version: 8, sources: {}, layers: [{ id: "cmdb-background", type: "background", paint: { "background-color": document.documentElement.dataset.theme === "light" ? "#e9ece8" : "#080909" } }] },
        bounds: [[-76,-37],[-32,8]], fitBoundsOptions: { padding: 36, maxZoom: 4.3 }, minZoom: 2.5, maxZoom: 8,
        renderWorldCopies: false, attributionControl: true, cooperativeGestures: false,
      });
      map.addControl(new window.mapboxgl.NavigationControl({ showCompass: false }), "top-right");
      loadingTimer = window.setTimeout(() => {
        if (!mapLoaded) showError("O mapa excedeu o tempo de carregamento. Verifique a conexão e tente novamente.");
      }, 20000);
      map.dragRotate.disable(); map.touchZoomRotate.disableRotation();
      map.on("load", () => {
        const features = geojson.features.map(feature => ({ ...feature, properties: { ...feature.properties, links: valueFor(feature.properties.sigla, aggregate[feature.properties.sigla] || { total_links: 0 }) } }));
        map.addSource("cmdb-states", { type: "geojson", data: { type: "FeatureCollection", features }, promoteId: "sigla" });
        map.addLayer({ id: "cmdb-fill", type: "fill", source: "cmdb-states", paint: { "fill-color": fillExpression(Math.max(1, ...features.map(feature => feature.properties.links))), "fill-opacity": .9 } });
        map.addLayer({ id: "cmdb-outline", type: "line", source: "cmdb-states", paint: { "line-color": document.documentElement.dataset.theme === "light" ? "#77827a" : "#758079", "line-width": 1 } });
        map.on("click", "cmdb-fill", event => { const code = event.features?.[0]?.properties?.sigla; if (code) selectState(code); });
        map.on("mouseenter", "cmdb-fill", () => { map.getCanvas().style.cursor = "pointer"; });
        map.on("mouseleave", "cmdb-fill", () => { map.getCanvas().style.cursor = ""; });
        const popup = new window.mapboxgl.Popup({ closeButton: false, closeOnClick: false, offset: 10 });
        map.on("mousemove", "cmdb-fill", event => {
          const code = event.features?.[0]?.properties?.sigla;
          if (!code) return;
          const row = aggregate[code] || { total_links: 0 };
          const demo = demoMetrics(code, row.total_links);
          const amount = valueFor(code, row);
          popup.setLngLat(event.lngLat).setHTML(`<strong>${escapeHtml(ufNames[code] || code)}</strong><br>${number.format(amount)} ${escapeHtml(metricLabel())}<br>${number.format(row.total_links)} links reais CMDB${metricFilter.value === "base" ? "" : `<br>${number.format(demo.tickets)} chamados demonstrativos`}`).addTo(map);
        });
        map.on("mouseleave", "cmdb-fill", () => popup.remove());
        message.hidden = true;
        mapLoaded = true;
        errorBox.hidden = true;
        window.clearTimeout(loadingTimer);
      });
      map.on("error", event => {
        if (!mapLoaded) {
          window.clearTimeout(loadingTimer);
          showError(event.error?.message || "Falha na inicialização do mapa.");
        }
      });
    } catch (error) { showError(error.message); }
  }
  operatorFilter.addEventListener("change", () => refresh().catch(error => showError(error.message)));
  projectFilter.addEventListener("change", () => refresh().catch(error => showError(error.message)));
  metricFilter.addEventListener("change", refreshMapView);
  periodFilter.addEventListener("change", refreshMapView);
  reasonFilter.addEventListener("change", refreshMapView);
  stateSearch.addEventListener("change", searchState);
  stateSearch.addEventListener("keydown", event => { if (event.key === "Enter") searchState(); });
  root.querySelector("[data-cmdb-panel-close]").addEventListener("click", () => { selectedCode = ""; statePanel.hidden = true; root.classList.remove("has-selection"); });
  root.querySelector("[data-cmdb-retry]").addEventListener("click", () => {
    window.clearTimeout(loadingTimer);
    errorBox.hidden = true;
    message.hidden = false;
    mapLoaded = false;
    if (map) map.remove();
    map = null;
    initialize();
  });
  window.addEventListener("arion:themechange", event => {
    if (!map || !mapLoaded) return;
    const light = event.detail?.theme === "light";
    if (map.getLayer("cmdb-background")) map.setPaintProperty("cmdb-background", "background-color", light ? "#e9ece8" : "#080909");
    if (map.getLayer("cmdb-outline")) map.setPaintProperty("cmdb-outline", "line-color", light ? "#77827a" : "#758079");
    const max = Math.max(1, ...Object.entries(aggregate).map(([uf,row]) => valueFor(uf,row)));
    if (map.getLayer("cmdb-fill")) map.setPaintProperty("cmdb-fill", "fill-color", fillExpression(max));
  });
  initialize();
})();
