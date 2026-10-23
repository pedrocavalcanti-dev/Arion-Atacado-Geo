(() => {
  const page = document.querySelector("[data-cockpit]");
  if (!page) return;

  const form = page.querySelector("[data-filters]");
  const FILTER_KEYS = ["operator", "project", "provider", "contract_operator", "uf", "status", "sla_status", "service"];
  const DEFAULTS = { metric: "tickets", period_from: "2026-01", period_to: "2026-10", compare_to: "", group_by: "operator", filters: Object.fromEntries(FILTER_KEYS.map(key => [key, "all"])) };
  const METRICS = { links: "Links CMDB", tickets: "Tickets", open_tickets: "Abertos", closed_tickets: "Resolvidos/encerrados", recurrences: "Links reincidentes", backlog: "Backlog aberto" };
  const DIMENSIONS = { operator: "Provedor", project: "Projeto (legado)", provider: "Provedor", contract_operator: "Operadora", uf: "UF", status: "Status", sla_status: "SLA", service: "Servi\u00e7o", month: "M\u00eas" };
  const MONTHS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out"];
  const number = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });
  const monthLabel = value => `${MONTHS[Number(value.slice(5)) - 1]}/2026`;
  const csrf = page.querySelector("[name=csrfmiddlewaretoken]")?.value || "";
  let queryState = readURLState();
  let activePreset = null;
  let latestRequest = 0;
  let controller = null;
  let latestResult = null;

  function cloneDefaults() { return { ...DEFAULTS, filters: { ...DEFAULTS.filters } }; }
  function validMonth(value) { return /^2026-(0[1-9]|10)$/.test(value || ""); }
  function readURLState() {
    const params = new URLSearchParams(location.search);
    const next = cloneDefaults();
    if (METRICS[params.get("metric")]) next.metric = params.get("metric");
    if (validMonth(params.get("period_from"))) next.period_from = params.get("period_from");
    if (validMonth(params.get("period_to") || params.get("period"))) next.period_to = params.get("period_to") || params.get("period");
    if (validMonth(params.get("compare_to"))) next.compare_to = params.get("compare_to");
    if (DIMENSIONS[params.get("group_by")]) next.group_by = params.get("group_by");
    FILTER_KEYS.forEach(key => { if (params.has(key) && params.get(key)) next.filters[key] = params.get(key); });
    if (next.period_from > next.period_to) next.period_from = next.period_to;
    if (next.compare_to && next.compare_to > next.period_to) next.compare_to = "";
    return next;
  }
  function queryPayload() {
    return { metric: queryState.metric, period: queryState.period_to, period_from: queryState.period_from, period_to: queryState.period_to, compare_to: queryState.compare_to || null, group_by: queryState.group_by, filters: { ...queryState.filters } };
  }
  function writeURL() {
    const params = new URLSearchParams();
    if (queryState.metric !== DEFAULTS.metric) params.set("metric", queryState.metric);
    if (queryState.period_from !== DEFAULTS.period_from) params.set("period_from", queryState.period_from);
    if (queryState.period_to !== DEFAULTS.period_to) params.set("period_to", queryState.period_to);
    if (queryState.compare_to) params.set("compare_to", queryState.compare_to);
    if (queryState.group_by !== DEFAULTS.group_by) params.set("group_by", queryState.group_by);
    FILTER_KEYS.forEach(key => { if (queryState.filters[key] !== "all") params.set(key, queryState.filters[key]); });
    history.replaceState(null, "", `${location.pathname}${params.size ? `?${params}` : ""}${location.hash}`);
  }
  function readForm() {
    queryState.metric = form.elements.metric.value;
    queryState.period_from = form.elements.period_from.value;
    queryState.period_to = form.elements.period_to.value;
    queryState.compare_to = form.elements.compare_to.value;
    queryState.group_by = form.elements.group_by.value;
    FILTER_KEYS.forEach(key => { queryState.filters[key] = form.elements.namedItem(key).value || "all"; });
  }
  function normalizeDimension() {
    const allowed = queryState.metric === "links" ? new Set(["month", "operator", "project", "provider", "uf"]) : new Set(Object.keys(DIMENSIONS));
    if (!allowed.has(queryState.group_by)) queryState.group_by = queryState.metric === "links" ? "operator" : "operator";
    for (const select of [form.elements.group_by, page.querySelector("[data-breakdown]")]) {
      [...select.options].forEach(option => { option.hidden = !allowed.has(option.value); });
      select.value = queryState.group_by;
    }
  }
  function syncForm() {
    normalizeDimension();
    for (const key of ["metric", "period_from", "period_to", "compare_to", "group_by"]) form.elements.namedItem(key).value = queryState[key];
    FILTER_KEYS.forEach(key => { form.elements.namedItem(key).value = queryState.filters[key]; });
    page.querySelector("[data-breakdown]").value = queryState.group_by;
    const advanced = FILTER_KEYS.slice(2).some(key => queryState.filters[key] !== "all") || queryState.group_by !== "operator";
    setMoreOpen(advanced);
  }
  function setMoreOpen(open) {
    const button = page.querySelector("[data-more-toggle]");
    const panel = page.querySelector("[data-more-filters]");
    panel.hidden = !open;
    button.setAttribute("aria-expanded", String(open));
    button.querySelector(".cockpit-more-symbol").textContent = open ? "-" : "+";
    button.querySelector("[data-more-label]").textContent = open ? "Menos filtros" : "Mais filtros";
  }
  function escapeHTML(value) { return String(value ?? "").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]); }
  async function post(url, payload, signal) {
    const response = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRFToken": csrf }, credentials: "same-origin", body: JSON.stringify(payload), signal });
    const type = response.headers.get("content-type") || "";
    const body = type.includes("application/json") ? await response.json() : null;
    if (!response.ok) throw new Error(body?.error?.message || body?.error || "Falha na solicitação.");
    return body;
  }
  function renderOptions(options = {}) {
    for (const [key, values] of Object.entries(options)) {
      const select = form.elements.namedItem(key);
      const value = queryState.filters[key];
      const first = select.options[0];
      const optionsList = [first, ...values.map(item => new Option(item, item))];
      if (value !== "all" && !values.includes(value)) optionsList.push(new Option(`${value} · fora das opções disponíveis`, value));
      select.replaceChildren(...optionsList);
      select.value = value;
    }
    const periods = Array.from({ length: 10 }, (_, index) => `2026-${String(index + 1).padStart(2, "0")}`);
    for (const key of ["period_from", "period_to", "compare_to"]) {
      const select = form.elements.namedItem(key);
      const opts = periods.map(value => new Option(`${MONTHS[Number(value.slice(5)) - 1]}/26`, value));
      if (key === "compare_to") opts.unshift(new Option("Sem comparação", ""));
      select.replaceChildren(...opts);
      select.value = queryState[key];
    }
  }
  function renderKpis(items) {
    const box = page.querySelector("[data-kpis]");
    box.innerHTML = items.map(item => `<article class="kpi-card dash-card" data-source="${item.source}"><span class="kpi-label">${escapeHTML(item.label)}</span><strong class="kpi-value">${number.format(item.value)}${escapeHTML(item.unit || "")}</strong><small class="kpi-note">${"Espelho local CMDB / OTRS"}</small></article>`).join("");
  }
  function renderSeries(data) {
    const box = page.querySelector("[data-series]");
    const points = data.series || [];
    const max = Math.max(1, ...points.map(item => Number(item.value)));
    const min = points.length ? Math.min(...points.map(item => Number(item.value))) : 0;
    const comparison = data.comparison;
    let selectedValues;
    if (points.length <= 12) selectedValues = new Set(points.map((_, index) => index));
    else if (points.length <= 24) selectedValues = new Set([...points.map((_, index) => index).filter(index => index % 2 === 0), points.findIndex(item => item.value === min), points.findIndex(item => item.value === max), points.length - 1]);
    else selectedValues = new Set([points.findIndex(item => item.value === min), points.findIndex(item => item.value === max), points.length - 1]);
    const bars = points.map((item, index) => {
      const month = Number(item.key.slice(5)) - 1;
      const height = Math.max(2, Number(item.value) / max * 100);
      const deltaLabel = comparison && queryState.compare_to ? `${queryState.compare_to}: ${number.format(comparison.value)}; ${comparison.difference > 0 ? "+" : ""}${number.format(comparison.difference)}${comparison.percent === null ? " (sem base percentual)" : ` (${comparison.percent > 0 ? "+" : ""}${number.format(comparison.percent)}%)`}` : "";
      const tooltip = `${MONTHS[month]}/2026 · ${number.format(item.value)} ${data.metric_label.toLowerCase()}${deltaLabel ? ` · Comparação ${deltaLabel}` : ""}`;
      return `<button class="cockpit-column" type="button" data-month="${item.key}" data-is-comparison="${item.key === queryState.compare_to}" data-is-current="${item.key === queryState.period_to}" aria-label="${escapeHTML(tooltip)}" title="${escapeHTML(tooltip)}"><span class="cockpit-bar-value" ${selectedValues.has(index) ? "" : "hidden"}>${number.format(item.value)}</span><i style="--bar-height:${height}%"></i><span>${MONTHS[month]}</span></button>`;
    }).join("");
    const hasData = points.some(item => Number(item.value) !== 0);
    box.innerHTML = points.length && hasData ? `<div class="cockpit-bars">${bars}</div>` : `<p class="cockpit-empty">Nenhum resultado encontrado para esta combinação de filtros.</p>`;
    page.querySelector("[data-trend-title]").textContent = `${data.metric_label} ao longo do período`;
    page.querySelector("[data-trend-context]").textContent = `${monthLabel(queryState.period_from)} a ${monthLabel(queryState.period_to)}`;
    page.querySelector("[data-chart-legend]").innerHTML = `<span><i></i>Período analisado</span>${comparison ? `<span><i class="is-comparison"></i>Comparação · ${escapeHTML(monthLabel(queryState.compare_to))} · ${number.format(comparison.value)}</span>` : ""}`;
    const comparisonNode = page.querySelector("[data-comparison]");
    if (!comparison) comparisonNode.textContent = "";
    else if (comparison.percent === null) comparisonNode.textContent = `Sem base comparável · ${comparison.difference > 0 ? "+" : ""}${number.format(comparison.difference)}`;
    else comparisonNode.textContent = `${comparison.difference > 0 ? "+" : ""}${number.format(comparison.difference)} (${comparison.percent > 0 ? "+" : ""}${number.format(comparison.percent)}%) vs ${MONTHS[Number(queryState.compare_to.slice(5)) - 1]}/26`;
  }
  function renderBreakdown(data) {
    const box = page.querySelector("[data-breakdown-list]");
    const detail = data.detail || [];
    page.querySelector("[data-detail-dimension]").textContent = DIMENSIONS[queryState.group_by] || "Dimensão";
    page.querySelector("[data-detail-metric]").textContent = data.metric_label;
    page.querySelector("[data-detail-total]").textContent = `${number.format(data.value)} ${data.metric_label.toLowerCase()}`;
    if (!detail.length || !data.value) {
      page.dataset.empty = "true";
      box.innerHTML = `<p class="cockpit-empty">Nenhum resultado encontrado para esta combinação de filtros.</p>`;
      page.querySelector("[data-detail-body]").innerHTML = `<tr><td colspan="3">Nenhum resultado para exibir.</td></tr>`;
      return;
    }
    page.dataset.empty = "false";
    const maximum = Math.max(1, ...detail.map(row => row.value));
    box.innerHTML = detail.map(row => `<button type="button" class="cockpit-break-row" data-drill="${escapeHTML(row.dimension)}"><span>${escapeHTML(row.dimension)}</span><i aria-hidden="true"><b style="--bar-width:${Math.max(2, row.value / maximum * 100)}%"></b></i><strong>${number.format(row.value)}</strong><small>${number.format(row.share)}%</small></button>`).join("");
    page.querySelector("[data-detail-body]").innerHTML = detail.map(row => `<tr><td>${escapeHTML(row.dimension)}</td><td>${number.format(row.value)}</td><td>${number.format(row.share)}%</td></tr>`).join("");
  }
  function renderActive() {
    const names = { operator: "Provedor", project: "Projeto (legado)", provider: "Provedor", contract_operator: "Operadora", uf: "UF", status: "Status", sla_status: "SLA", service: "Servi\u00e7o" };
    const chips = FILTER_KEYS.filter(key => queryState.filters[key] !== "all").map(key => `${names[key]}: ${queryState.filters[key]}`);
    chips.unshift(`${METRICS[queryState.metric]}`, `${monthLabel(queryState.period_from)} a ${monthLabel(queryState.period_to)}`);
    if (queryState.compare_to) chips.push(`Comparado a ${queryState.compare_to}`);
    chips.push(`Por ${DIMENSIONS[queryState.group_by]}`);
    const preset = activePreset ? ` · ${activePreset.label}${activePreset.modified ? " · modificada" : ""}` : "";
    page.querySelector("[data-active-filters]").textContent = chips.join(" · ") + preset;
    const summary = page.querySelector("[data-query-summary]");
    summary.innerHTML = chips.map((chip, index) => `<span class="cockpit-summary-chip${index < 2 ? " is-primary" : ""}">${escapeHTML(chip)}</span>`).join("") + (preset ? `<span class="cockpit-summary-chip">${escapeHTML(preset.trim().replace(/^·\s*/, ""))}</span>` : "");
    summary.title = chips.join(" · ") + preset;
    page.querySelectorAll("[data-quick]").forEach(button => {
      const active = activePreset?.key === button.dataset.quick;
      button.classList.toggle("is-active", Boolean(active));
      button.setAttribute("aria-pressed", String(Boolean(active)));
      button.dataset.modified = String(Boolean(active && activePreset.modified));
    });
  }
  function setLoading(loading) {
    page.dataset.loading = String(loading);
    page.querySelector("[data-status]").textContent = loading ? "Atualizando análise…" : "";
  }
  function prepareLoading() {
    page.querySelector("[data-kpis]").replaceChildren();
    page.querySelector("[data-series]").innerHTML = `<p class="cockpit-empty">Atualizando a série…</p>`;
    page.querySelector("[data-breakdown-list]").innerHTML = `<p class="cockpit-empty">Atualizando a distribuição…</p>`;
    page.querySelector("[data-detail-body]").innerHTML = `<tr><td colspan="3">Atualizando detalhamento…</td></tr>`;
  }
  async function refresh() {
    const requestId = ++latestRequest;
    controller?.abort();
    controller = new AbortController();
    const thisController = controller;
    page.querySelector("[data-error]").hidden = true;
    setLoading(true);
    prepareLoading();
    writeURL();
    renderActive();
    try {
      const result = await post(page.dataset.queryUrl, queryPayload(), thisController.signal);
      if (requestId !== latestRequest) return;
      latestResult = result;
      renderOptions(result.options);
      renderKpis(result.kpis || []);
      renderSeries(result);
      renderBreakdown(result);
      page.dataset.metric = result.metric;
      page.dataset.dimension = queryState.group_by;
      renderActive();
    } catch (error) {
      if (error.name !== "AbortError" && requestId === latestRequest) {
        page.querySelector("[data-error]").hidden = false;
        page.querySelector("[data-status]").textContent = "";
      }
    } finally {
      if (requestId === latestRequest) setLoading(false);
    }
  }
  function presetState(key) {
    const presets = {
      finance: { metric: "tickets", group_by: "service", label: "Tickets por servi\u00e7o" },
      recurrence: { metric: "recurrences", group_by: "operator", label: "Reincid\u00eancia" },
      sla: { metric: "tickets", group_by: "sla_status", label: "Tickets por SLA" },
      backlog: { metric: "backlog", group_by: "operator", label: "Backlog por operadora" },
      project: { metric: "tickets", group_by: "project", label: "Tickets por projeto legado" },
      reasons: { metric: "tickets", group_by: "status", label: "Tickets por status" }
    };
    const preset = presets[key];
    queryState = cloneDefaults();
    queryState.metric = preset.metric;
    queryState.group_by = preset.group_by;
    Object.assign(queryState.filters, preset.filters || {});
    activePreset = { key, label: preset.label, modified: false };
    syncForm();
    refresh();
  }
  function updatePresetStatus() {
    if (!activePreset) return;
    const expected = presetStateSnapshot(activePreset.key);
    activePreset.modified = JSON.stringify(queryPayload()) !== JSON.stringify(expected);
  }
  function presetStateSnapshot(key) {
    const presets = {
      finance: ["tickets", "service", null], recurrence: ["recurrences", "operator", null],
      sla: ["tickets", "sla_status", null], backlog: ["backlog", "operator", null],
      project: ["tickets", "project", null], reasons: ["tickets", "status", null]
    }[key];
    const expected = cloneDefaults();
    expected.metric = presets[0]; expected.group_by = presets[1];
    if (presets[2]) expected.filters.service = presets[2];
    return { metric: expected.metric, period: expected.period_to, period_from: expected.period_from, period_to: expected.period_to, compare_to: expected.compare_to || null, group_by: expected.group_by, filters: expected.filters };
  }
  async function loadSaved() {
    const data = await post(page.dataset.savedUrl, { action: "list" });
    const box = page.querySelector("[data-saved-list]");
    box.innerHTML = data.views.length ? data.views.map(view => `<article class="cockpit-saved-row"><button type="button" class="cockpit-saved-name" data-open="${view.id}">${escapeHTML(view.name)}</button><div><button type="button" data-rename="${view.id}" data-name="${escapeHTML(view.name)}">Renomear</button><button type="button" data-delete="${view.id}">Excluir</button></div></article>`).join("") : `<p class="cockpit-empty">Ainda não há consultas salvas.</p>`;
  }
  function initSavedViews() {
    const panel = page.querySelector("[data-saved-panel]");
    if (!panel) return;
    page.querySelector("[data-saved-toggle]").addEventListener("click", async () => { panel.hidden = !panel.hidden; if (!panel.hidden) try { await loadSaved(); } catch (_) { showStatusError("Não foi possível carregar suas consultas salvas."); } });
    page.querySelector("[data-saved-close]").addEventListener("click", () => { panel.hidden = true; });
    const saveDialog = page.querySelector("[data-save-dialog]"), saveForm = page.querySelector("[data-save-form]");
    page.querySelector("[data-save-open]").addEventListener("click", () => saveDialog.showModal());
    page.querySelector("[data-dialog-close]").addEventListener("click", () => saveDialog.close());
    saveForm.addEventListener("submit", async event => {
      event.preventDefault();
      try { await post(page.dataset.savedUrl, { action: "save", name: new FormData(saveForm).get("name"), configuration: queryPayload() }); saveDialog.close(); saveForm.reset(); panel.hidden = false; await loadSaved(); }
      catch (_) { showStatusError("Não foi possível salvar esta consulta."); }
    });
    const renameDialog = page.querySelector("[data-rename-dialog]"), renameForm = page.querySelector("[data-rename-form]");
    page.querySelector("[data-rename-close]").addEventListener("click", () => renameDialog.close());
    panel.addEventListener("click", async event => {
      const open = event.target.closest("[data-open]"), remove = event.target.closest("[data-delete]"), rename = event.target.closest("[data-rename]");
      try {
        if (open) {
          const { views } = await post(page.dataset.savedUrl, { action: "list" });
          const saved = views.find(view => String(view.id) === open.dataset.open);
          if (!saved) return;
          queryState = { ...cloneDefaults(), ...saved.configuration, filters: { ...cloneDefaults().filters, ...(saved.configuration.filters || {}) } };
          activePreset = null; syncForm(); panel.hidden = true; refresh();
        } else if (remove) {
          await post(page.dataset.savedUrl, { action: "delete", id: remove.dataset.delete }); await loadSaved();
        } else if (rename) {
          renameForm.elements.id.value = rename.dataset.rename; renameForm.elements.name.value = rename.dataset.name; renameDialog.showModal(); renameForm.elements.name.focus();
        }
      } catch (_) { showStatusError("Não foi possível atualizar suas consultas salvas."); }
    });
    renameForm.addEventListener("submit", async event => {
      event.preventDefault();
      try { await post(page.dataset.savedUrl, { action: "rename", id: renameForm.elements.id.value, name: renameForm.elements.name.value }); renameDialog.close(); await loadSaved(); }
      catch (_) { showStatusError("Não foi possível renomear esta consulta."); }
    });
  }
  function showStatusError(message) { page.querySelector("[data-status]").textContent = message; }
  async function exportCurrent(format) {
    const button = page.querySelector(`[data-export="${format}"]`);
    button.disabled = true;
    try {
      const response = await fetch(page.dataset.exportUrl, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRFToken": csrf }, credentials: "same-origin", body: JSON.stringify({ ...queryPayload(), format }) });
      if (!response.ok) { const body = await response.json(); throw new Error(body.error?.message || body.error || "Falha na exportação."); }
      const blob = await response.blob(), href = URL.createObjectURL(blob), link = document.createElement("a");
      link.href = href; link.download = response.headers.get("content-disposition")?.match(/filename="?([^";]+)"?/i)?.[1] || `arion-cockpit.${format}`;
      document.body.append(link); link.click(); link.remove(); URL.revokeObjectURL(href);
    } catch (_) { showStatusError("Não foi possível exportar esta análise."); }
    finally { button.disabled = false; }
  }
  function clearFilters() {
    controller?.abort();
    queryState = cloneDefaults(); activePreset = null; syncForm(); refresh();
  }

  form.addEventListener("change", () => { readForm(); syncForm(); updatePresetStatus(); refresh(); });
  form.addEventListener("submit", event => { event.preventDefault(); readForm(); syncForm(); updatePresetStatus(); refresh(); });
  page.querySelector("[data-more-toggle]").addEventListener("click", event => {
    const open = event.currentTarget.getAttribute("aria-expanded") !== "true";
    setMoreOpen(open);
  });
  page.querySelector("[data-clear]").addEventListener("click", clearFilters);
  page.querySelector("[data-retry]").addEventListener("click", refresh);
  page.querySelector("[data-breakdown]").addEventListener("change", event => { queryState.group_by = event.target.value; form.elements.group_by.value = queryState.group_by; updatePresetStatus(); refresh(); });
  page.querySelectorAll("[data-quick]").forEach(button => button.addEventListener("click", () => presetState(button.dataset.quick)));
  page.addEventListener("click", event => {
    const month = event.target.closest("[data-month]"), drill = event.target.closest("[data-drill]");
    if (month) {
      queryState.period_to = month.dataset.month;
      if (queryState.period_from > queryState.period_to) queryState.period_from = queryState.period_to;
      if (queryState.compare_to === queryState.period_to) queryState.compare_to = "";
      syncForm(); updatePresetStatus(); refresh();
    } else if (drill) {
      const key = queryState.group_by;
      if (FILTER_KEYS.includes(key)) { queryState.filters[key] = drill.dataset.drill; syncForm(); updatePresetStatus(); refresh(); }
      else if (key === "month") { queryState.period_from = drill.dataset.drill; queryState.period_to = drill.dataset.drill; syncForm(); updatePresetStatus(); refresh(); }
    }
  });
  const exportOptions = page.querySelector("[data-export-options]"), exportToggle = page.querySelector("[data-export-toggle]");
  exportToggle.addEventListener("click", () => { exportOptions.hidden = !exportOptions.hidden; exportToggle.setAttribute("aria-expanded", String(!exportOptions.hidden)); });
  exportOptions.addEventListener("click", event => { const button = event.target.closest("[data-export]"); if (button) { exportOptions.hidden = true; exportToggle.setAttribute("aria-expanded", "false"); exportCurrent(button.dataset.export); } });
  window.addEventListener("popstate", () => { queryState = readURLState(); activePreset = null; syncForm(); refresh(); });

  syncForm();
  initSavedViews();
  refresh();
})();
