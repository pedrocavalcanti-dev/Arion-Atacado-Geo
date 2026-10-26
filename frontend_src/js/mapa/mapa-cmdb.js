(() => {
  const page = document.querySelector(".geo-page");
  if (!page) return;
  const root = page.querySelector("[data-cmdb-map]");
  if (!root) {
    console.error("O template do Mapa n\u00e3o possui o palco [data-cmdb-map].");
    return;
  }
  const number = new Intl.NumberFormat("pt-BR");
  const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
  const mapElement = document.getElementById("brazil-map");
  const message = root.querySelector("[data-cmdb-message]");
  const errorBox = root.querySelector("[data-cmdb-error]");
  const statePanel = root.querySelector("[data-cmdb-state-panel]");
  // Toolbar controls live in the page header, outside the map stage.
  const operatorFilter = page.querySelector("[data-cmdb-operator]");
  const projectFilter = page.querySelector("[data-cmdb-project]");
  const metricFilter = page.querySelector("[data-cmdb-metric]");
  const dateFrom = page.querySelector("[data-cmdb-date-from]");
  const dateTo = page.querySelector("[data-cmdb-date-to]");
  const stateSearch = page.querySelector("[data-cmdb-state-search]");
  const errorDetail = root.querySelector("[data-cmdb-error-detail]");
  // KPI and note live in the page header, outside the map stage.
  const totalElement = page.querySelector("[data-cmdb-total]");
  const ufNote = page.querySelector("[data-cmdb-uf-note]");
  const stateList = root.querySelector("[data-cmdb-state-list]");
  const stateName = root.querySelector("[data-cmdb-state-name]");
  const stateTotal = root.querySelector("[data-cmdb-state-total]");
  const stateOperators = root.querySelector("[data-cmdb-state-operators]");
  const stateProjects = root.querySelector("[data-cmdb-state-projects]");
  const sourceNote = page.querySelector("[data-cmdb-source-note]");
  const totalLabel = page.querySelector("[data-cmdb-total-label]");
  const stateMetricLabel = root.querySelector("[data-cmdb-state-metric-label]");
  const stateContext = root.querySelector("[data-cmdb-state-context]");
  const errorTitle = root.querySelector("[data-cmdb-error-title]");
  const panelClose = root.querySelector("[data-cmdb-panel-close]");
  const retry = root.querySelector("[data-cmdb-retry]");
  const required = [mapElement, message, errorBox, statePanel, operatorFilter, projectFilter,
    metricFilter, dateFrom, dateTo, stateSearch, totalElement, totalLabel, ufNote, sourceNote,
    stateList, errorDetail, errorTitle, stateName, stateTotal, stateOperators, stateProjects,
    stateMetricLabel, stateContext, panelClose, retry];
  const ufNames = { AC:"Acre",AL:"Alagoas",AM:"Amazonas",AP:"Amap\u00e1",BA:"Bahia",CE:"Cear\u00e1",DF:"Distrito Federal",ES:"Esp\u00edrito Santo",GO:"Goi\u00e1s",MA:"Maranh\u00e3o",MG:"Minas Gerais",MS:"Mato Grosso do Sul",MT:"Mato Grosso",PA:"Par\u00e1",PB:"Para\u00edba",PE:"Pernambuco",PI:"Piau\u00ed",PR:"Paran\u00e1",RJ:"Rio de Janeiro",RN:"Rio Grande do Norte",RO:"Rond\u00f4nia",RR:"Roraima",RS:"Rio Grande do Sul",SC:"Santa Catarina",SE:"Sergipe",SP:"S\u00e3o Paulo",TO:"Tocantins" };
  let map;
  let mapLoaded = false;
  let initializeSequence = 0;
  let loadingTimer;
  let geojson;
  let aggregate = {};
  let viewData = {};
  let selectedCode = "";
  let refreshSequence = 0;
  function valueFor(_uf, row) {
    return ({ base: row.total_links || 0, tickets: row.ticket_count || 0,
      open_tickets: row.open_tickets || 0, affected_links: row.affected_links || 0,
      recurrences: row.recurrence_links || 0 })[metricFilter.value] || 0;
  }
  function metricLabel() {
    return ({ base: "links CMDB", tickets: "tickets operacionais no per\u00edodo", open_tickets: "tickets ativos",
      affected_links: "links com ticket ativo", recurrences: "links com 2+ tickets no per\u00edodo" })[metricFilter.value];
  }
  function refreshMapView() {
    try { localStorage.setItem("arion-cmdb-map-state", JSON.stringify({ metric: metricFilter.value })); } catch (_error) { /* Map use does not depend on storage. */ }
    sourceNote.textContent = metricFilter.value === "base"
      ? "Base: CMDB real \u00b7 snapshot atual."
      : `${metricLabel()} \u00b7 OTRS local \u00b7 data baseada na cria\u00e7\u00e3o do ticket.`;
    totalLabel.textContent = metricLabel();
    if (!geojson || !viewData.states) return;
    updateMap(viewData);
    if (selectedCode) selectState(selectedCode);
  }

  function showError(text, title = "N\u00e3o foi poss\u00edvel carregar os dados do mapa.") {
    if (message) message.hidden = true;
    if (errorBox) errorBox.hidden = false;
    if (errorTitle) errorTitle.textContent = title;
    if (errorDetail) errorDetail.textContent = text;
  }
  if (required.some(element => !element)) {
    console.error("O template do Mapa est\u00e1 sem um elemento obrigat\u00f3rio; confira os seletores data-cmdb-*.");
    showError("A estrutura do mapa est\u00e1 incompleta. Atualize a p\u00e1gina ou tente novamente.");
    return;
  }
  try {
    const saved = JSON.parse(localStorage.getItem("arion-cmdb-map-state") || "{}");
    if (["base", "tickets", "open_tickets", "affected_links", "recurrences"].includes(saved.metric)) metricFilter.value = saved.metric;
  } catch (_error) { /* Map use does not depend on storage. */ }
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
    const metricTotals = { base: filteredTotal, tickets: data.ticket_count, open_tickets: data.active_ticket_count, affected_links: data.affected_link_count, recurrences: data.recurrence_link_count };
    totalElement.textContent = number.format(metricTotals[metricFilter.value] ?? valueTotal);
    ufNote.textContent = `${number.format(data.valid_uf_count ?? (filteredTotal - (data.invalid_uf_count || 0)))} links agregados por UF; ${number.format(data.invalid_uf_count || 0)} sem UF v\u00e1lida.`;
    const displayRanked = Object.entries(aggregate).map(([uf, row]) => [uf, { ...row, value: valueFor(uf, row) }]).sort((a,b) => b[1].value-a[1].value);
    stateList.innerHTML = displayRanked.slice(0, 10).map(([uf, row], index) => `<div class="cmdb-state-rank"><span>${String(index + 1).padStart(2,"0")}</span><b>${ufNames[uf] || uf}</b><small>${uf}</small><strong>${number.format(row.value)}</strong><i><em style="width:${row.value / max * 100}%"></em></i></div>`).join("") || "<p>Nenhum link com UF v\u00e1lida.</p>";
  }
  function fillFilters(data) {
    operatorFilter.innerHTML = '<option value="">Todas</option>' + data.operators.map(item => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)}</option>`).join("");
    projectFilter.innerHTML = '<option value="">Todos</option>' + data.projects.map(name => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join("");
  }
  async function refresh() {
    const requestId = ++refreshSequence;
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
    if (requestId !== refreshSequence) return false;
    fillFilters(data);
    operatorFilter.value = url.searchParams.get("operator") || "";
    projectFilter.value = url.searchParams.get("project") || "";
    viewData = data;
    refreshMapView();
    return true;
  }
  function selectState(code) {
    selectedCode = code;
    const row = aggregate[code] || { total_links: 0, operator_counts: {}, project_counts: {} };
    root.classList.add("has-selection");
    statePanel.hidden = false;
    stateName.textContent = `${ufNames[code] || code} \u00b7 ${code}`;
    stateTotal.textContent = number.format(valueFor(code, row));
    stateMetricLabel.textContent = metricLabel();
    stateContext.textContent = `${number.format(row.total_links || 0)} links CMDB \u00b7 ${number.format(row.ticket_count || 0)} tickets no per\u00edodo \u00b7 ${number.format(row.open_tickets || 0)} tickets ativos \u00b7 ${number.format(row.affected_links || 0)} links com ticket ativo.`;
    const countsHtml = (counts, empty) => Object.entries(counts || {}).sort((a,b) => b[1] - a[1]).map(([name, count]) => `<div class="operator-row"><span>${escapeHtml(name)}</span><strong>${number.format(count)}</strong><i class="operator-meter"><b style="width:${row.total_links ? count / row.total_links * 100 : 0}%"></b></i></div>`).join("") || `<p class="value-muted">${empty}</p>`;
    stateOperators.innerHTML = countsHtml(row.operator_counts, "Provedor n\u00e3o identificado.");
    stateProjects.innerHTML = countsHtml(row.project_counts, "Projeto n\u00e3o informado.");
  }
  function searchState() {
    const query = stateSearch.value.trim().toLocaleUpperCase("pt-BR");
    if (!query || !geojson) return;
    const normalized = value => String(value).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleUpperCase("pt-BR");
    const code = Object.keys(ufNames).find(uf => normalized(uf) === normalized(query) || normalized(ufNames[uf]) === normalized(query));
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
    const attempt = ++initializeSequence;
    window.clearTimeout(loadingTimer);
    mapLoaded = false;
    if (map) map.remove();
    map = null;
    if (!root.dataset.token) return showError("Token Mapbox n\u00e3o configurado.", "Mapa indispon\u00edvel");
    if (!window.mapboxgl) return showError("N\u00e3o foi poss\u00edvel carregar Mapbox GL JS. Verifique a conex\u00e3o.", "Mapa indispon\u00edvel");
    message.hidden = false;
    errorBox.hidden = true;
    try {
      const geoResponse = await fetch(root.dataset.geojsonUrl, { signal: AbortSignal.timeout(15000) });
      if (!geoResponse.ok) throw new Error("GeoJSON indisponivel.");
      const loadedGeojson = await geoResponse.json();
      if (attempt !== initializeSequence) return;
      if (loadedGeojson.type !== "FeatureCollection" || !Array.isArray(loadedGeojson.features)) throw new Error("GeoJSON em formato inesperado.");
      geojson = loadedGeojson;
      await refresh();
      if (attempt !== initializeSequence) return;
      window.mapboxgl.accessToken = root.dataset.token;
      map = new window.mapboxgl.Map({
        container: mapElement,
        style: { version: 8, sources: {}, layers: [{ id: "cmdb-background", type: "background", paint: { "background-color": document.documentElement.dataset.theme === "light" ? "#e9ece8" : "#080909" } }] },
        bounds: [[-76,-37],[-32,8]], fitBoundsOptions: { padding: 36, maxZoom: 4.3 }, minZoom: 2.5, maxZoom: 8,
        renderWorldCopies: false, attributionControl: true, cooperativeGestures: false,
      });
      map.addControl(new window.mapboxgl.NavigationControl({ showCompass: false }), "top-right");
      loadingTimer = window.setTimeout(() => {
        if (!mapLoaded && attempt === initializeSequence) showError("O mapa demorou para responder. Verifique a conex\u00e3o e tente novamente.");
      }, 20000);
      map.dragRotate.disable(); map.touchZoomRotate.disableRotation();
      map.on("load", () => {
        if (attempt !== initializeSequence || !map) return;
        try {
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
            popup.setLngLat(event.lngLat).setHTML(`<strong>${escapeHtml(ufNames[code] || code)}</strong><br>${number.format(amount)} ${escapeHtml(metricLabel())}<br>${number.format(row.total_links || 0)} links CMDB<br>${number.format(row.open_tickets || 0)} tickets ativos`).addTo(map);
          });
          map.on("mouseleave", "cmdb-fill", () => popup.remove());
          refreshMapView();
          message.hidden = true;
          mapLoaded = true;
          errorBox.hidden = true;
          window.clearTimeout(loadingTimer);
        } catch (error) {
          mapLoaded = false;
          window.clearTimeout(loadingTimer);
          console.error("Falha ao montar as camadas do Mapa", error);
          showError("Nao foi possivel montar o mapa. Tente novamente.");
        }
      });
      map.on("error", event => {
        if (!mapLoaded && attempt === initializeSequence) {
          window.clearTimeout(loadingTimer);
          console.error("Falha Mapbox no Mapa", event.error || event);
          showError("Verifique o token p\u00fablico e a conex\u00e3o com o Mapbox.", "Mapa indispon\u00edvel");
        }
      });
    } catch (error) {
      if (attempt !== initializeSequence) return;
      console.error("Falha ao inicializar o Mapa", error);
      showError("N\u00e3o foi poss\u00edvel carregar os dados do mapa. Tente novamente.");
    }
  }
  const refreshFromFilters = () => refresh().catch(error => {
    console.error("Falha ao atualizar os filtros do Mapa", error);
    showError("N\u00e3o foi poss\u00edvel carregar os dados do mapa. Tente novamente.");
  });
  operatorFilter.addEventListener("change", refreshFromFilters);
  projectFilter.addEventListener("change", refreshFromFilters);
  metricFilter.addEventListener("change", refreshMapView);
  dateFrom.addEventListener("change", refreshFromFilters);
  dateTo.addEventListener("change", refreshFromFilters);
  stateSearch.addEventListener("change", searchState);
  stateSearch.addEventListener("keydown", event => { if (event.key === "Enter") searchState(); });
  panelClose.addEventListener("click", () => { selectedCode = ""; statePanel.hidden = true; root.classList.remove("has-selection"); });
  retry.addEventListener("click", initialize);
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
