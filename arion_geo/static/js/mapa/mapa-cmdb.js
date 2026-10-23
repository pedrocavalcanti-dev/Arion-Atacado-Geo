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
  const dateFrom = root.querySelector("[data-cmdb-date-from]");
  const dateTo = root.querySelector("[data-cmdb-date-to]");
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
    metricFilter, dateFrom, dateTo, stateSearch,
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
  try {
    const saved = JSON.parse(localStorage.getItem("arion-cmdb-map-state") || "{}");
    if (["base", "tickets", "open_tickets", "affected_links", "recurrences"].includes(saved.metric)) metricFilter.value = saved.metric;
  } catch (_error) { /* Map use does not depend on storage. */ }
  function valueFor(_uf, row) {
    return ({ base: row.total_links || 0, tickets: row.ticket_count || 0,
      open_tickets: row.open_tickets || 0, affected_links: row.affected_links || 0,
      recurrences: row.recurrence_links || 0 })[metricFilter.value] || 0;
  }
  function metricLabel() {
    return ({ base: "links CMDB", tickets: "tickets criados no período", open_tickets: "tickets abertos",
      affected_links: "links com ticket aberto", recurrences: "links com 2+ tickets no período" })[metricFilter.value];
  }
  function refreshMapView() {
    try { localStorage.setItem("arion-cmdb-map-state", JSON.stringify({ metric: metricFilter.value })); } catch (_error) { /* Map use does not depend on storage. */ }
    if (sourceNote) sourceNote.textContent = metricFilter.value === "base"
      ? "Base: CMDB real · snapshot atual."
      : `${metricLabel()} · OTRS local · data baseada na criação do ticket.`;
    if (totalLabel) totalLabel.textContent = metricLabel();
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
    const valueTotal = Object.entries(aggregate).reduce((sum, [uf, row]) => sum + valueFor(uf, row), 0);
    const filteredTotal = data.filtered_source_total ?? data.source_total ?? 0;
    totalElement.textContent = number.format(metricFilter.value === "base" ? filteredTotal : valueTotal);
    ufNote.textContent = `${number.format(filteredTotal - (data.invalid_uf_count || 0))} links com UF válida; ${number.format(data.invalid_uf_count || 0)} sem UF válida. Tickets usam o recorte de data informado.`;
    const displayRanked = Object.entries(aggregate).map(([uf, row]) => [uf, { ...row, value: valueFor(uf, row) }]).sort((a,b) => b[1].value-a[1].value);
    stateList.innerHTML = displayRanked.slice(0, 10).map(([uf, row], index) => `<div class="cmdb-state-rank"><span>${String(index + 1).padStart(2,"0")}</span><b>${ufNames[uf] || uf}</b><small>${uf}</small><strong>${number.format(row.value)}</strong><i><em style="width:${row.value / max * 100}%"></em></i></div>`).join("") || '<p>Nenhum link com UF válida.</p>';
  }
  function fillFilters(data) {
    operatorFilter.innerHTML = '<option value="">Todas</option>' + data.operators.map(item => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)}</option>`).join("");
    projectFilter.innerHTML = '<option value="">Todos</option>' + data.projects.map(name => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join("");
  }
  async function refresh() {
    const url = new URL(root.dataset.apiUrl, window.location.origin);
    if (operatorFilter.value) url.searchParams.set("operator", operatorFilter.value);
    if (projectFilter.value) url.searchParams.set("project", projectFilter.value);
    if (dateFrom.value) url.searchParams.set("date_from", dateFrom.value);
    if (dateTo.value) url.searchParams.set("date_to", dateTo.value);
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
    if (stateMetricLabel) stateMetricLabel.textContent = metricLabel();
    if (stateContext) stateContext.textContent = `${number.format(row.total_links || 0)} links CMDB ? ${number.format(row.ticket_count || 0)} tickets no período ? ${number.format(row.open_tickets || 0)} abertos agora ? ${number.format(row.affected_links || 0)} links afetados.`;
    const countsHtml = (counts, empty) => Object.entries(counts || {}).sort((a,b) => b[1] - a[1]).map(([name, count]) => `<div class="operator-row"><span>${escapeHtml(name)}</span><strong>${number.format(count)}</strong><i class="operator-meter"><b style="width:${row.total_links ? count / row.total_links * 100 : 0}%"></b></i></div>`).join("") || `<p class="value-muted">${empty}</p>`;
    stateOperators.innerHTML = countsHtml(row.operator_counts, "Provedor nao classificado.");
    stateProjects.innerHTML = countsHtml(row.project_counts, "Projeto nao classificado.");
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
          const amount = valueFor(code, row);
          popup.setLngLat(event.lngLat).setHTML(`<strong>${escapeHtml(ufNames[code] || code)}</strong><br>${number.format(amount)} ${escapeHtml(metricLabel())}<br>${number.format(row.total_links || 0)} links CMDB<br>${number.format(row.open_tickets || 0)} tickets abertos`).addTo(map);
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
  dateFrom.addEventListener("change", () => refresh().catch(error => showError(error.message)));
  dateTo.addEventListener("change", () => refresh().catch(error => showError(error.message)));
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
