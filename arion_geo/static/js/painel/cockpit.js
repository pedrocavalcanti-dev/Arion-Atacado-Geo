(() => {
  const page = document.querySelector("[data-cockpit]");
  if (!page) return;

  const form = page.querySelector("[data-filters]");
  const FILTER_KEYS = ["provider", "uf", "status", "source_state", "service", "sla", "priority", "termination_reason"];
  const ADVANCED_KEYS = ["source_state", "uf", "sla", "priority", "service"];
  const DEFAULT_START = page.dataset.defaultStart;
  const DEFAULT_END = page.dataset.defaultEnd;
  const DEFAULTS = { metric: "tickets", start: DEFAULT_START, end: DEFAULT_END, compare_to: "", selected_month: "", group_by: "provider", detail_page: 1, ticket_page: 1, ticket_page_size: 25, ticket_search: "", filters: Object.fromEntries(FILTER_KEYS.map(key => [key, "all"])) };
  const METRICS = { tickets: "Tickets criados", open_tickets: "Em atendimento no per\u00edodo", pending_tickets: "Pendentes no per\u00edodo", scheduled_tickets: "Agendados no per\u00edodo", resolved_tickets: "Resolvidos no per\u00edodo", closed_tickets: "Encerrados no per\u00edodo", resolved_closed_tickets: "Resolvidos + Encerrados", canceled_tickets: "Cancelados no per\u00edodo", links_affected: "Links afetados", recurrences: "Links reincidentes", backlog: "Backlog atual" };
  const DIMENSIONS = { provider: "Provedor", uf: "UF", status: "Status", source_state: "Situa\u00e7\u00e3o OTRS", sla: "SLA", priority: "Prioridade", termination_reason: "Motivo de encerramento", month: "Per\u00edodo" };
  const FILTER_LABELS = { ...DIMENSIONS, service: "Servi\u00e7o" };
  const MONTHS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
  const STATE_CODES = new Set(["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"]);
  const STATE_NAMES = { AC: "acre", AL: "alagoas", AP: "amapa", AM: "amazonas", BA: "bahia", CE: "ceara", DF: "distrito federal", ES: "espirito santo", GO: "goias", MA: "maranhao", MT: "mato grosso", MS: "mato grosso do sul", MG: "minas gerais", PA: "para", PB: "paraiba", PR: "parana", PE: "pernambuco", PI: "piaui", RJ: "rio de janeiro", RN: "rio grande do norte", RS: "rio grande do sul", RO: "rondonia", RR: "roraima", SC: "santa catarina", SP: "sao paulo", SE: "sergipe", TO: "tocantins" };
  function stateCode(value) {
    const raw = String(value || "").trim().toUpperCase();
    if (STATE_CODES.has(raw)) return raw;
    const normalized = String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toLowerCase();
    return Object.keys(STATE_NAMES).find(code => STATE_NAMES[code] === normalized) || "";
  }
  const number = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });
  const percentage = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const monthLabel = value => `${MONTHS[Number(value.slice(5)) - 1]}/${value.slice(2, 4)}`;
  const dateLabel = value => { const [year, month, day] = value.split("-"); return `${day}/${month}/${year}`; };
  const csrf = page.querySelector("[name=csrfmiddlewaretoken]")?.value || "";
  let queryState = readURLState();
  let monthExplicitlySelected = Boolean(queryState.selected_month);
  let activePreset = null;
  let latestRequest = 0;
  let controller = null;
  let temporaryTicketDay = "";
  let selectedDayForDialog = null;
  const DETAIL_COLLAPSE_DEFAULTS = { dimensions: false, distribution: true, tickets: false };
  const DETAIL_COLLAPSE_STORAGE_KEY = "arion.cockpit.detail-collapse.v1";
  let detailCollapseState = readDetailCollapseState();
  let sourceStateLabels = new Map();

  function readDetailCollapseState() {
    try {
      const saved = JSON.parse(sessionStorage.getItem(DETAIL_COLLAPSE_STORAGE_KEY) || "{}");
      return Object.fromEntries(Object.entries(DETAIL_COLLAPSE_DEFAULTS).map(([key, fallback]) => [key, typeof saved[key] === "boolean" ? saved[key] : fallback]));
    } catch (_) { return { ...DETAIL_COLLAPSE_DEFAULTS }; }
  }
  function writeDetailCollapseState() {
    try { sessionStorage.setItem(DETAIL_COLLAPSE_STORAGE_KEY, JSON.stringify(detailCollapseState)); } catch (_) { /* session storage can be unavailable in private contexts */ }
  }
  function updateGlobalCollapseControl() {
    const button = page.querySelector("[data-details-global]");
    if (!button) return;
    const allCollapsed = Object.keys(DETAIL_COLLAPSE_DEFAULTS).every(key => detailCollapseState[key]);
    const label = button.querySelector("[data-details-global-label]");
    if (label) label.textContent = allCollapsed ? "Expandir detalhes" : "Recolher detalhes";
    button.setAttribute("aria-expanded", String(!allCollapsed));
  }
  function setDetailCollapsed(key, collapsed, persist = true) {
    const panel = page.querySelector(`[data-collapse-panel="${key}"]`), button = page.querySelector(`[data-collapse-toggle="${key}"]`);
    if (!panel || !button) return;
    detailCollapseState[key] = Boolean(collapsed);
    panel.classList.toggle("is-collapsed", detailCollapseState[key]);
    panel.setAttribute("aria-hidden", String(detailCollapseState[key]));
    panel.inert = detailCollapseState[key];
    button.setAttribute("aria-expanded", String(!detailCollapseState[key]));
    if (persist) writeDetailCollapseState();
    updateGlobalCollapseControl();
  }
  function initDetailCollapses() {
    Object.keys(DETAIL_COLLAPSE_DEFAULTS).forEach(key => setDetailCollapsed(key, detailCollapseState[key], false));
    page.querySelectorAll("[data-collapse-toggle]").forEach(button => {
      button.addEventListener("click", () => {
        const key = button.dataset.collapseToggle;
        setDetailCollapsed(key, !detailCollapseState[key]);
      });
    });
    const globalButton = page.querySelector("[data-details-global]");
    globalButton?.addEventListener("click", () => {
      const collapse = !Object.keys(DETAIL_COLLAPSE_DEFAULTS).every(key => detailCollapseState[key]);
      Object.keys(DETAIL_COLLAPSE_DEFAULTS).forEach(key => setDetailCollapsed(key, collapse));
    });
  }

  function cloneDefaults() { return { ...DEFAULTS, filters: { ...DEFAULTS.filters } }; }
  function validDate(value) { return /^\d{4}-\d{2}-\d{2}$/.test(value || "") && !Number.isNaN(Date.parse(`${value}T00:00:00Z`)); }
  function validMonth(value) { return /^\d{4}-(0[1-9]|1[0-2])$/.test(value || ""); }
  function monthRange(value) {
    const [year, month] = value.split("-").map(Number), last = new Date(Date.UTC(year, month, 0)).getUTCDate();
    return [`${value}-01`, `${value}-${String(last).padStart(2, "0")}`];
  }
  function readURLState() {
    const params = new URLSearchParams(location.search), state = cloneDefaults();
    const legacyGroups = { operator: "provider", project: "provider", service: "provider", sla_status: "sla", contract_operator: null, isp: null };
    if (METRICS[params.get("metric")]) state.metric = params.get("metric");
    if (validDate(params.get("start"))) state.start = params.get("start");
    else if (validMonth(params.get("period_from"))) state.start = `${params.get("period_from")}-01`;
    if (validDate(params.get("end"))) state.end = params.get("end");
    else {
      const oldEnd = params.get("period_to") || params.get("period");
      if (validMonth(oldEnd)) state.end = monthRange(oldEnd)[1];
    }
    if (validMonth(params.get("compare_to"))) state.compare_to = params.get("compare_to");
    if (validMonth(params.get("selected_month"))) state.selected_month = params.get("selected_month");
    const group = legacyGroups[params.get("group_by")] ?? params.get("group_by");
    if (DIMENSIONS[group]) state.group_by = group;
    FILTER_KEYS.forEach(key => { if (params.has(key)) state.filters[key] = params.get(key) || "all"; });
    if (params.has("closing_reason") && !params.has("termination_reason")) state.filters.termination_reason = params.get("closing_reason") || "all";
    if (!params.has("provider") && params.has("operator")) state.filters.provider = params.get("operator") || "all";
    if (!params.has("sla") && params.has("sla_status")) state.filters.sla = params.get("sla_status") || "all";
    if (state.start > state.end) state.start = state.end;
    state.ticket_page = Math.max(1, Number(params.get("ticket_page")) || 1);
    state.ticket_page_size = [25, 50, 100].includes(Number(params.get("ticket_page_size"))) ? Number(params.get("ticket_page_size")) : 25;
    state.ticket_search = (params.get("ticket_search") || "").slice(0, 120);
    const pageNumber = Number(params.get("detail_page"));
    state.detail_page = Number.isInteger(pageNumber) && pageNumber > 0 ? pageNumber : 1;
    return state;
  }
  function normalizeState(state) {
    const legacyGroups = { operator: "provider", project: "provider", service: "provider", sla_status: "sla", contract_operator: null, isp: null };
    state.metric = state.metric === "links" || !METRICS[state.metric] ? "tickets" : state.metric;
    state.group_by = legacyGroups[state.group_by] ?? state.group_by;
    if (!DIMENSIONS[state.group_by]) state.group_by = "provider";
    if (!validDate(state.start) && validMonth(state.period_from)) state.start = `${state.period_from}-01`;
    if (!validDate(state.end) && validMonth(state.period_to)) state.end = monthRange(state.period_to)[1];
    state.start = validDate(state.start) ? state.start : DEFAULT_START;
    state.end = validDate(state.end) ? state.end : DEFAULT_END;
    if (state.start > state.end) state.start = state.end;
    state.selected_month = validMonth(state.selected_month) ? state.selected_month : "";
    const oldFilters = state.filters || {};
    state.filters = Object.fromEntries(FILTER_KEYS.map(key => [key, oldFilters[key] ?? "all"]));
    if (state.filters.provider === "all" && oldFilters.operator) state.filters.provider = oldFilters.operator;
    if (state.filters.sla === "all" && oldFilters.sla_status) state.filters.sla = oldFilters.sla_status;
    state.detail_page = 1;
    state.ticket_page = Math.max(1, Number(state.ticket_page) || 1);
    state.ticket_page_size = [25, 50, 100].includes(Number(state.ticket_page_size)) ? Number(state.ticket_page_size) : 25;
    state.ticket_search = String(state.ticket_search || "").slice(0, 120);
    return state;
  }
  function queryPayload() {
    return { metric: queryState.metric, start: queryState.start, end: queryState.end, compare_to: queryState.compare_to || null, selected_month: monthExplicitlySelected ? queryState.selected_month || null : null, group_by: queryState.group_by, detail_page: queryState.detail_page, ticket_page: queryState.ticket_page, ticket_page_size: queryState.ticket_page_size, ticket_search: queryState.ticket_search, filters: { ...queryState.filters } };
  }
  function writeURL() {
    const params = new URLSearchParams();
    if (queryState.metric !== DEFAULTS.metric) params.set("metric", queryState.metric);
    if (queryState.start !== DEFAULTS.start) params.set("start", queryState.start);
    if (queryState.end !== DEFAULTS.end) params.set("end", queryState.end);
    if (queryState.compare_to) params.set("compare_to", queryState.compare_to);
    if (monthExplicitlySelected && queryState.selected_month) params.set("selected_month", queryState.selected_month);
    if (queryState.group_by !== DEFAULTS.group_by) params.set("group_by", queryState.group_by);
    if (queryState.detail_page > 1) params.set("detail_page", queryState.detail_page);
    if (queryState.ticket_page > 1) params.set("ticket_page", queryState.ticket_page);
    if (queryState.ticket_page_size !== 25) params.set("ticket_page_size", queryState.ticket_page_size);
    if (queryState.ticket_search) params.set("ticket_search", queryState.ticket_search);
    FILTER_KEYS.forEach(key => { if (queryState.filters[key] !== "all") params.set(key, queryState.filters[key]); });
    history.replaceState(null, "", `${location.pathname}${params.size ? `?${params}` : ""}${location.hash}`);
  }
  function readForm() {
    queryState.metric = form.elements.metric.value;
    queryState.start = form.elements.start.value || DEFAULT_START;
    queryState.end = form.elements.end.value || DEFAULT_END;
    queryState.compare_to = form.elements.compare_to.value;
    queryState.group_by = page.querySelector("[data-breakdown]").value;
    FILTER_KEYS.forEach(key => { queryState.filters[key] = form.elements.namedItem(key).value || "all"; });
  }
  function syncForm() {
    for (const key of ["metric", "start", "end", "compare_to"]) form.elements.namedItem(key).value = queryState[key];
    FILTER_KEYS.forEach(key => { form.elements.namedItem(key).value = queryState.filters[key]; });
    page.querySelector("[data-breakdown]").value = queryState.group_by;
    const snapshot = queryState.metric === "backlog";
    form.elements.start.disabled = snapshot;
    form.elements.end.disabled = snapshot;
    updateMoreFilters();
  }
  function updateMoreFilters() {
    const count = ADVANCED_KEYS.filter(key => queryState.filters[key] !== "all").length + Number(Boolean(queryState.compare_to));
    page.querySelector("[data-more-label]").textContent = count ? `Mais filtros Â· ${count} ativo${count === 1 ? "" : "s"}` : "Mais filtros";
    if (count) page.querySelector("[data-more-filters]").open = true;
  }
  function escapeHTML(value) { return String(value ?? "").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]); }
  async function post(url, payload, signal) {
    const response = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRFToken": csrf }, credentials: "same-origin", body: JSON.stringify(payload), signal });
    const body = (response.headers.get("content-type") || "").includes("application/json") ? await response.json() : null;
    if (!response.ok) throw new Error(body?.error?.message || body?.error || "Falha na solicita\u00e7\u00e3o.");
    return body;
  }
  function renderOptions(options = {}) {
    for (const [key, values] of Object.entries(options)) {
      const select = form.elements.namedItem(key);
      if (!select) continue;
      const selected = queryState.filters[key], first = select.options[0];
      const normalized = values.map(item => typeof item === "object" ? item : { value: item, label: item });
      const list = [first, ...normalized.map(item => new Option(item.label, item.value))];
      if (selected === "high-critical" && key === "priority") list.push(new Option("Alto / Cr\u00edtico", selected));
      else if (selected !== "all" && !normalized.some(item => item.value === selected)) {
        const friendly = { CANCELED: "Cancelado", UNKNOWN: "N\u00e3o classificado" }[selected] || selected;
        list.push(new Option(`${friendly} \u00b7 fora das op\u00e7\u00f5es dispon\u00edveis`, selected));
      }
      select.replaceChildren(...list);
      select.value = selected;
      if (key === "source_state") sourceStateLabels = new Map(normalized.map(item => [String(item.value), String(item.label)]));
    }
    form.elements.compare_to.value = queryState.compare_to;
  }
  function renderKpis(items) {
    const help = {
      coverage: "Percentual dos tickets da análise que possuem vínculo com um provedor identificado no CMDB.",
      unresolved: "Tickets da análise cujo vínculo OTRS → ConfigItem → Link → Provedor não pôde ser concluído."
    };
    page.querySelector("[data-kpis]").innerHTML = (items || []).slice(0, 4).map(item => {
      const value = item.unit === "% dos tickets" ? `${number.format(item.value)}%` : number.format(item.value);
      const trend = item.trend;
      const sign = trend?.absolute_change > 0 ? "+" : "";
      const trendValue = trend ? (trend.unit === "p.p." ? `${sign}${number.format(trend.absolute_change)} p.p.` : item.key === "total" && trend.percentage_change !== null ? `${sign}${number.format(trend.percentage_change)}% vs período anterior` : `${sign}${number.format(trend.absolute_change)} vs período anterior`) : "";
      const trendClass = trend?.favorable === true ? "is-favorable" : trend?.favorable === false ? "is-unfavorable" : "is-neutral";
      const note = item.unit === "% dos tickets" ? "dos tickets encontrados" : item.unit || "";
      return `<article class="kpi-card dash-card" title="${escapeHTML(help[item.key] || "Resumo calculado conforme a consulta ativa.")}"><span class="kpi-label">${escapeHTML(item.label)}</span><strong class="kpi-value">${value}</strong><small class="kpi-note">${escapeHTML(note)}</small>${trend ? `<span class="cockpit-kpi-trend ${trendClass}" aria-label="Variação ${escapeHTML(trendValue)}">${trend.direction === "up" ? "↑" : trend.direction === "down" ? "↓" : "·"} ${escapeHTML(trendValue)}</span>` : ""}</article>`;
    }).join("");
  }
  function renderSeries(data) {
    const specs = data.chart_specs || [];
    const overview = specs.find(spec => spec.type === "temporal_overview");
    const dimensions = specs.filter(spec => spec.type !== "temporal_overview" && spec.type !== "monthly_calendar");
    const overviewGrid = page.querySelector("[data-overview-grid]");
    const dimensionGrid = page.querySelector("[data-dimension-grid]");
    overviewGrid.innerHTML = overview ? renderOverview(overview, data.time_grain) : '<p class="cockpit-empty">A consulta não apresenta variação temporal suficiente.</p>';
    dimensionGrid.innerHTML = dimensions.length ? dimensions.map(renderDimension).join("") : '<p class="cockpit-empty">Não há dimensões complementares relevantes para esta consulta.</p>';
    renderCalendar(data.temporal);
    const baseLabels = { tickets: "data de criação", open_tickets: "data de criação", pending_tickets: "data de criação", scheduled_tickets: "data de criação", resolved_tickets: "data de encerramento", closed_tickets: "data de encerramento", resolved_closed_tickets: "data terminal", canceled_tickets: "data de cancelamento", backlog: "snapshot atual" };
    const base = page.querySelector("[data-period-semantics]");
    base.textContent = `Base: ${baseLabels[data.metric] || "data de criação"}`;
    base.title = data.metric === "canceled_tickets" ? "Métrica específica de cancelamentos." : data.metric === "backlog" ? "Backlog considera tickets atuais em atendimento, pendentes ou agendados." : "Considera estados operacionais válidos; tickets cancelados e estados não classificados são excluídos.";
    const reason = queryState.filters.termination_reason;
    const title = reason && data.metric_label ? `${data.metric_label} por ${reason}` : data.description?.title || "Análise do Cockpit";
    page.querySelector("[data-analysis-title]").textContent = title;
    const snapshot = data.metric === "backlog";
    page.querySelector("[data-current-period]").textContent = snapshot ? "Snapshot atual" : `${dateLabel(data.start_date || queryState.start)} → ${dateLabel(data.end_date || queryState.end)}`;
    page.querySelector("[data-current-analysis]").title = data.description?.subtitle || title;
    const comparison = data.comparison, node = page.querySelector("[data-comparison]");
    if (!comparison) { node.replaceChildren(); node.removeAttribute("title"); }
    else {
      const previous = comparison.previous_start && comparison.previous_end ? `${dateLabel(comparison.previous_start)} a ${dateLabel(comparison.previous_end)}` : monthLabel(queryState.compare_to);
      const change = comparison.percentage_change === null ? `${number.format(comparison.absolute_change)} tickets` : `${percentage.format(comparison.percentage_change)}%`;
      node.replaceChildren();
      const value = document.createElement("strong"), label = document.createElement("small");
      value.textContent = `${comparison.direction === "up" ? "↑" : comparison.direction === "down" ? "↓" : "·"} ${change}`;
      label.textContent = "vs período anterior";
      node.append(value, label); node.title = previous;
    }
  }
  function renderOverview(spec, grain) {
    const values = spec.values || [], labels = spec.labels || [], details = spec.details || [];
    const max = Math.max(1, ...values.map(Number));
    const monthly = grain === "month";
    const points = values.map((value, index) => {
      const item = details[index] || { label: labels[index], value, share: 0 };
      const month = monthly && /^\d{4}-\d{2}$/.test(item.key || "") ? `data-chart-month="${escapeHTML(item.key)}"` : "";
      const clickable = month ? "is-navigable" : "";
      const share = `${number.format(item.share || 0)}% do período`;
      const previous = item.previous_value;
      const comparison = previous === null || previous === undefined ? "" : previous === 0 ? "Novo no período" : `${number.format(value - previous)} vs período anterior`;
      const accessible = `${item.label}: ${number.format(value)} ${spec.unit || "tickets"}; ${share}${month ? "; selecionar este mês no calendário" : ""}`;
      return `<button type="button" class="cockpit-column cockpit-overview-point ${clickable}" ${month} data-chart-point aria-label="${escapeHTML(accessible)}"><span class="cockpit-bar-value">${number.format(value)}</span><i style="--bar-height:${Math.max(2, Number(value) / max * 100)}%"></i><span>${escapeHTML(labels[index])}</span><span class="cockpit-point-tooltip" role="tooltip"><strong>${escapeHTML(item.label)}</strong><span>${number.format(value)} ${escapeHTML(spec.unit || "tickets")}</span><small>${share}</small>${comparison ? `<small>${escapeHTML(comparison)}</small>` : ""}</span></button>`;
    }).join("");
    return `<article class="cockpit-chart-card cockpit-overview-card" data-chart-key="${escapeHTML(spec.key)}"><header><h3>${escapeHTML(spec.title)}</h3><p>${escapeHTML(spec.subtitle || "")}${monthly ? " · Selecione um mês para abrir o calendário" : ""}</p></header><div class="cockpit-chart" aria-label="${escapeHTML(spec.title)}"><div class="cockpit-bars" role="list" style="--series-count:${values.length}">${points}</div></div></article>`;
  }
  function renderDimension(spec) {
    const details = spec.details || [], unit = spec.unit || "tickets";
    const rows = details.map((item, index) => {
      const width = Math.max(item.value ? 2 : 0, Math.min(100, Number(item.value) / Math.max(1, ...details.map(row => Number(row.value))) * 100));
      const accessible = `${item.label}: ${number.format(item.value)} ${unit}, ${number.format(item.share || 0)}%`;
      if (spec.type === "ranking") {
        let label = escapeHTML(item.label);
        if (spec.dimension === "uf") {
          const code = stateCode(item.key || item.label);
          const flag = code
            ? `<img class="cockpit-uf-flag" src="/static/imagens/bandeiras/estados/${code.toLowerCase()}.svg" alt="" loading="lazy">`
            : "";
          label = `${flag}<span class="cockpit-uf-code">${escapeHTML(code || item.label)}</span>`;
        }
        return `<li title="${escapeHTML(accessible)}" aria-label="${escapeHTML(accessible)}"><span class="cockpit-rank-position">${index + 1}</span><strong>${label}</strong><span>${number.format(item.value)} ${escapeHTML(unit)}</span><small>${number.format(item.share || 0)}%</small></li>`;
      }
      return `<li title="${escapeHTML(accessible)}"><strong>${escapeHTML(item.label)}</strong><span class="cockpit-horizontal-track"><i style="--bar-width:${width}%"></i></span><span>${number.format(item.value)} ${escapeHTML(unit)}</span><small>${number.format(item.share || 0)}%</small></li>`;
    }).join("");
    const listClass = spec.type === "ranking" ? "cockpit-provider-ranking" : "cockpit-horizontal-list";
    const tag = spec.type === "ranking" ? "ol" : "ul";
    return `<article class="cockpit-chart-card cockpit-dimension-card ${spec.type === "ranking" ? "cockpit-ranking-card" : ""}" data-chart-key="${escapeHTML(spec.key)}" data-chart-type="${escapeHTML(spec.type)}"><header><h3>${escapeHTML(spec.title)}</h3><p>${escapeHTML(spec.subtitle || "")}</p></header><${tag} class="${listClass}">${rows || `<li>Nenhum resultado para ${escapeHTML(spec.title.toLowerCase())}.</li>`}</${tag}></article>`;
  }
  function renderCalendar(temporal) {
    const section = page.querySelector("[data-calendar]"), select = page.querySelector("[data-month-select]"), grid = page.querySelector("[data-calendar-grid]");
    if (!temporal || !temporal.selected_month) { section.hidden = true; return; }
    section.hidden = false;
    page.dataset.calendarUnit = temporal.unit || "tickets";
    queryState.selected_month = temporal.selected_month;
    const selected = (temporal.available_months || []).find(item => item.key === temporal.selected_month);
    const summary = temporal.month_summary || {}, monthTitle = temporal.selected_month_label || selected?.label || monthLabel(temporal.selected_month);
    page.querySelector("[data-calendar-title]").textContent = `Detalhe de ${monthTitle}`;
    page.querySelector("[data-calendar-subtitle]").textContent = `Distribuição diária de ${temporal.unit || "tickets"} da consulta.`;
    select.replaceChildren(...(temporal.available_months || []).map(item => new Option(item.label, item.key)));
    select.value = temporal.selected_month;
    const peak = summary.peak_day ? `${dateLabel(summary.peak_day)} · ${number.format(summary.peak_value)} ${temporal.unit || "tickets"}` : "Sem ocorrências";
    const indicators = [
      [`${number.format(summary.total || 0)} ${temporal.unit || "tickets"}`, "no mês selecionado"],
      [number.format(summary.average_per_day || 0), `média por dia · ${number.format(summary.days_in_query_period || 0)} dias no período`],
      [peak, `${number.format(summary.days_with_occurrence || 0)} dias com ocorrência`],
    ];
    page.querySelector("[data-calendar-summary]").innerHTML = indicators.map(([value, label]) => `<div><strong>${escapeHTML(value)}</strong><small>${escapeHTML(label)}</small></div>`).join("");
    const weekdays = temporal.weekdays || ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];
    const skeleton = `<div class="cockpit-calendar-skeleton" data-calendar-skeleton aria-hidden="true">${"<span></span>".repeat(42)}</div>`;
    grid.innerHTML = `<div class="cockpit-calendar-weekdays" role="row">${weekdays.map(day => `<span role="columnheader">${escapeHTML(day)}</span>`).join("")}</div>${(temporal.calendar_weeks || []).map((week, weekIndex) => `<div class="cockpit-calendar-week" role="row">${cellsForWeek(week, weekIndex, temporal, monthTitle)}</div>`).join("")}${skeleton}`;
    section.dataset.calendarLoading = "false";
  }
  function cellsForWeek(week, _weekIndex, temporal, monthTitle) {
    return week.map(day => {
      if (!day.inside_month) return '<span class="cockpit-calendar-day is-outside" aria-hidden="true"></span>';
      const count = Number(day.value || 0), strength = `${4 + Number(day.intensity || 0) * 19}%`;
      const label = day.accessible_label || `${day.day} de ${monthTitle}, ${number.format(count)} ${temporal.unit || "tickets"}`;
      const title = `${label} · ${number.format(day.share_of_month || 0)}% do mês`;
      const content = `<span class="cockpit-calendar-date">${day.day}</span><strong>${number.format(count)}</strong><small>${escapeHTML(temporal.unit || "tickets")}</small>`;
      return day.inside_query_period
        ? `<button type="button" class="cockpit-calendar-day${count ? " has-data" : " is-empty"}" data-calendar-day="${escapeHTML(day.date)}" data-day-value="${count}" style="--day-strength:${strength}" title="${escapeHTML(title)}" aria-label="${escapeHTML(label)}">${content}</button>`
        : `<span class="cockpit-calendar-day is-disabled" title="Fora do período analisado" aria-label="${escapeHTML(label)}">${content}</span>`;
    }).join("");
  }
  function renderPagination(data) {
    const nav = page.querySelector("[data-detail-pagination]"), current = Number(data.detail_page || 1), pages = Number(data.detail_pages || 1), total = Number(data.detail_total || 0);
    nav.innerHTML = `<span>${number.format(total)} grupos · Página ${number.format(current)} de ${number.format(pages)}</span><div><button type="button" data-detail-page="${Math.max(1, current - 1)}" ${current <= 1 ? "disabled" : ""}>Anterior</button><button type="button" data-detail-page="${Math.min(pages, current + 1)}" ${current >= pages ? "disabled" : ""}>Próxima</button></div>`;
  }
  function renderBreakdown(data) {
    const detail = data.detail || [], groupName = DIMENSIONS[queryState.group_by] || "dimensão";
    page.querySelector("[data-breakdown-title]").textContent = `Distribuição completa por ${groupName.toLowerCase()}`;
    page.querySelector("[data-detail-dimension]").textContent = groupName;
    page.querySelector("[data-detail-metric]").textContent = data.metric_label;
    const unit = ["links_affected", "recurrences"].includes(data.metric) ? "links" : "tickets";
    page.querySelector("[data-detail-groups]").textContent = `${number.format(data.detail_total)} grupos`;
    page.querySelector("[data-detail-total]").textContent = `${number.format(data.detail_total)} grupos · ${number.format(data.value)} ${unit}`;
    page.querySelector("[data-detail-body]").innerHTML = detail.length ? detail.map(row => `<tr><td>${escapeHTML(row.dimension)}</td><td>${number.format(row.value)}</td><td>${number.format(row.share)}%</td></tr>`).join("") : '<tr><td colspan="3">Nenhum resultado para exibir.</td></tr>';
    const quality = data.provider_quality || {}, qualityNote = page.querySelector("[data-provider-quality]");
    if (queryState.group_by === "provider" && quality.unresolved) {
      const causes = quality.unresolved_causes || {};
      qualityNote.textContent = `${number.format(quality.unresolved)} tickets sem provedor identificado; cobertura ${number.format(quality.coverage_percent)}%. Causas: sem relação ${number.format(causes.no_config_item || 0)}, sem espelho ${number.format(causes.missing_mirror || 0)}, link inválido ${number.format(causes.invalid_link || 0)}, link sem provedor ${number.format(causes.link_without_provider || 0)}.`;
    } else qualityNote.textContent = "";
    renderPagination(data);
  }
  function renderTickets(data) {
    const records = data.tickets || [], body = page.querySelector("[data-ticket-body]");
    const sourceTag = row => `<span class="cockpit-source-tag" title="${escapeHTML(row.source === "OTRS + CMDB" ? "Ticket OTRS com vínculo CMDB resolvido" : "Dados do espelho OTRS")}">${row.source === "OTRS + CMDB" ? "OTRS + CMDB" : "OTRS"}</span>`;
    body.innerHTML = records.length ? records.map(row => `<tr data-ticket-row="${row.id}"><td><button type="button" class="cockpit-ticket-link" data-ticket-open="${row.id}">${escapeHTML(row.ticket)}</button><span class="cockpit-ticket-source">${sourceTag(row)}</span></td><td>${escapeHTML(row.base_date)}</td><td>${escapeHTML(row.created_at)}</td><td>${escapeHTML(row.status)}</td><td title="${escapeHTML(row.source_state)}">${escapeHTML(sourceStateLabels.get(String(row.source_state)) || row.source_state)}</td><td>${escapeHTML(row.reason)}</td><td>${escapeHTML(row.provider)}</td><td>${escapeHTML(row.uf)}</td><td>${escapeHTML(row.priority)}</td><td>${escapeHTML(row.sla)}</td></tr>`).join("") : '<tr><td colspan="10">Nenhum ticket corresponde a esta consulta.</td></tr>';
    const search = page.querySelector("[data-ticket-search]");
    if (search.value !== (data.ticket_search || "")) search.value = data.ticket_search || "";
    page.querySelector("[data-ticket-size]").value = String(data.ticket_page_size || 25);
    const dayNote = page.querySelector("[data-ticket-day-active]");
    dayNote.hidden = !data.ticket_day;
    if (data.ticket_day) {
      temporaryTicketDay = data.ticket_day;
      page.querySelector("[data-ticket-day-label]").textContent = `Visualização temporária de ${dateLabel(data.ticket_day)} · ${number.format(data.ticket_day_total || 0)} tickets. A análise principal continua com ${number.format(data.ticket_result_total)} tickets.`;
      page.querySelector("[data-ticket-count]").textContent = `${number.format(data.ticket_day_total || 0)} tickets no dia`;
    } else {
      temporaryTicketDay = "";
      page.querySelector("[data-ticket-count]").textContent = `${number.format(data.ticket_result_total)} tickets`;
    }
    const current = Number(data.ticket_page || 1), pages = Number(data.ticket_pages || 1), nav = page.querySelector("[data-ticket-pagination]");
    nav.innerHTML = `<span>Página ${number.format(current)} de ${number.format(pages)}</span><div><button type="button" data-ticket-page="${Math.max(1, current - 1)}" ${current <= 1 ? "disabled" : ""}>Anterior</button><button type="button" data-ticket-page="${Math.min(pages, current + 1)}" ${current >= pages ? "disabled" : ""}>Próxima</button></div>`;
    page._cockpitTicketRows = new Map(records.map(row => [String(row.id), row]));
  }
  function openTicket(id) {
    const row = page._cockpitTicketRows?.get(String(id)), dialog = page.querySelector("[data-ticket-drawer]");
    if (!row || !dialog) return;
    dialog.querySelector("[data-drawer-title]").textContent = `Ticket ${row.ticket}`;
    dialog.querySelector("[data-drawer-status]").textContent = `${row.status} · ${sourceStateLabels.get(String(row.source_state)) || row.source_state}`;
    const details = [["Criado em", row.created_at], ["Alterado em", row.changed_at], ["Base da análise", row.base_date], ["Resolvido em", row.resolved_at], ["Encerrado em", row.terminal_at], ["Cancelado em", row.canceled_at], ["Motivo de encerramento", row.reason], ["Prioridade", row.priority], ["SLA", row.sla]];
    dialog.querySelector("[data-drawer-fields]").innerHTML = details.map(([label,value]) => `<div><dt>${escapeHTML(label)}</dt><dd>${escapeHTML(value || "—")}</dd></div>`).join("");
    dialog.querySelector("[data-drawer-links]").innerHTML = row.links?.length ? row.links.map(link => `<article><strong>ConfigItem ${escapeHTML(link.config_item_id)}</strong><dl><div><dt>Number</dt><dd>${escapeHTML(link.number || "—")}</dd></div><div><dt>Designação</dt><dd>${escapeHTML(link.designation || "—")}</dd></div><div><dt>Circuito</dt><dd>${escapeHTML(link.circuit || "—")}</dd></div><div><dt>Provedor</dt><dd>${escapeHTML(link.provider || "Não identificado")}</dd></div><div><dt>UF</dt><dd>${escapeHTML(link.uf || "—")}</dd></div></dl></article>`).join("") : "<p>Sem vínculo CMDB disponível.</p>";
    dialog.querySelector("[data-drawer-evidence]").innerHTML = (row.evidence || []).map(item => `<li>${escapeHTML(item)}</li>`).join("");
    dialog.showModal();
  }
  function renderActive() {
    const chips = FILTER_KEYS.filter(key => queryState.filters[key] !== "all").map(key => `${FILTER_LABELS[key]}: ${form.elements.namedItem(key).selectedOptions[0]?.textContent || queryState.filters[key]}`);
    if (queryState.compare_to) chips.push(`Comparado a ${monthLabel(queryState.compare_to)}`);
    const preset = activePreset ? ` \u00b7 ${activePreset.label}${activePreset.modified ? " \u00b7 modificada" : ""}` : "";
    const activeFilters = page.querySelector("[data-active-filters]");
    if (activeFilters) activeFilters.textContent = chips.join(" \u00b7 ") + preset;
    const summary = page.querySelector("[data-query-summary]");
    summary.innerHTML = chips.map(chip => `<span class="cockpit-summary-chip">${escapeHTML(chip)}</span>`).join("") + (preset ? `<span class="cockpit-summary-chip">${escapeHTML(preset.trim().replace(/^\u00b7\s*/, ""))}</span>` : "");
    summary.title = chips.join(" \u00b7 ") + preset;
    page.querySelectorAll("[data-quick]").forEach(button => {
      const active = activePreset?.key === button.dataset.quick;
      button.classList.toggle("is-active", Boolean(active));
      button.setAttribute("aria-pressed", String(Boolean(active)));
      button.dataset.modified = String(Boolean(active && activePreset.modified));
    });
  }
  function setLoading(loading) {
    page.dataset.loading = String(loading);
    page.querySelector("[data-status]").textContent = loading ? "Aplicando filtros..." : "";
    const apply = form.querySelector('[type="submit"]');
    if (apply) { apply.disabled = loading; apply.textContent = loading ? "Aplicando filtros..." : "Aplicar análise"; }
  }
  function prepareLoading() {
    if (page.dataset.resultsReady !== "true") {
      page.dataset.initialLoading = "true";
      return;
    }
    page.querySelector("[data-results-loading]").hidden = false;
    const calendar = page.querySelector("[data-calendar]");
    if (calendar && !calendar.hidden) calendar.dataset.calendarLoading = "true";
  }
  async function refresh() {
    const requestId = ++latestRequest;
    controller?.abort(); controller = new AbortController();
    page.querySelector("[data-error]").hidden = true;
    setLoading(true); prepareLoading(); writeURL(); renderActive();
    try {
      const payload = queryPayload();
      if (temporaryTicketDay) payload.ticket_day = temporaryTicketDay;
      const result = await post(page.dataset.queryUrl, payload, controller.signal);
      if (requestId !== latestRequest) return;
      renderOptions(result.options); renderKpis(result.kpis || []); renderSeries(result); renderBreakdown(result); renderTickets(result);
      writeURL();
      queryState.detail_page = result.detail_page || 1;
      page.dataset.metric = result.metric; page.dataset.dimension = queryState.group_by; page.dataset.initialLoading = "false"; page.dataset.resultsReady = "true"; renderActive();
    } catch (error) {
      if (error.name !== "AbortError" && requestId === latestRequest) { page.querySelector("[data-error]").hidden = false; page.querySelector("[data-status]").textContent = ""; }
    } finally { if (requestId === latestRequest) { setLoading(false); page.querySelector("[data-results-loading]").hidden = true; page.querySelector("[data-calendar]").dataset.calendarLoading = "false"; } }
  }
  const PRESETS = {
    finance: { metric: "closed_tickets", group_by: "provider", label: "Pend\u00eancia Financeira", filters: { termination_reason: "Pend\u00eancia Financeira" } },
    reason: { metric: "closed_tickets", group_by: "termination_reason", label: "Tickets por Motivo" },
    recurrence: { metric: "recurrences", group_by: "provider", label: "Reincidencia" },
    backlog: { metric: "backlog", group_by: "provider", label: "Backlog por Provedor" },
    status: { metric: "tickets", group_by: "status", label: "Tickets por Status" },
    "high-critical": { metric: "tickets", group_by: "priority", label: "Alto / Critico", filters: { priority: "high-critical" } },
  };
  function presetState(key) {
    const preset = PRESETS[key]; if (!preset) return;
    const start = queryState.start, end = queryState.end;
    monthExplicitlySelected = false;
    queryState = cloneDefaults(); queryState.metric = preset.metric; queryState.group_by = preset.group_by;
    queryState.start = start; queryState.end = end;
    if (preset.filters) Object.assign(queryState.filters, preset.filters);
    activePreset = { key, label: preset.label, modified: false };
    syncForm(); refresh();
  }
  function updatePresetStatus() {
    if (!activePreset) return;
    const preset = PRESETS[activePreset.key];
    activePreset.modified = queryState.metric !== preset.metric || queryState.group_by !== preset.group_by || FILTER_KEYS.some(key => queryState.filters[key] !== (preset.filters?.[key] || "all")) || queryState.start !== DEFAULT_START || queryState.end !== DEFAULT_END || Boolean(queryState.compare_to);
  }
  async function loadSaved() {
    const data = await post(page.dataset.savedUrl, { action: "list" });
    const box = page.querySelector("[data-saved-list]");
    box.innerHTML = data.views.length ? data.views.map(view => `<article class="cockpit-saved-row"><button type="button" class="cockpit-saved-name" data-open="${view.id}">${escapeHTML(view.name)}</button><div><button type="button" data-rename="${view.id}" data-name="${escapeHTML(view.name)}">Renomear</button><button type="button" data-delete="${view.id}">Excluir</button></div></article>`).join("") : '<p class="cockpit-empty">Ainda n\u00e3o h\u00e1 consultas salvas.</p>';
  }
  function initSavedViews() {
    const panel = page.querySelector("[data-saved-panel]"); if (!panel) return;
    page.querySelector("[data-saved-toggle]").addEventListener("click", async () => { panel.hidden = !panel.hidden; if (!panel.hidden) try { await loadSaved(); } catch (_) { showStatusError("N\u00e3o foi poss\u00edvel carregar suas consultas salvas."); } });
    page.querySelector("[data-saved-close]").addEventListener("click", () => { panel.hidden = true; });
    const saveDialog = page.querySelector("[data-save-dialog]"), saveForm = page.querySelector("[data-save-form]");
    page.querySelector("[data-save-open]").addEventListener("click", () => saveDialog.showModal());
    page.querySelector("[data-dialog-close]").addEventListener("click", () => saveDialog.close());
    saveForm.addEventListener("submit", async event => {
      event.preventDefault();
      try { const configuration = queryPayload(); delete configuration.detail_page; delete configuration.ticket_page; delete configuration.ticket_page_size; delete configuration.ticket_search; await post(page.dataset.savedUrl, { action: "save", name: new FormData(saveForm).get("name"), configuration }); saveDialog.close(); saveForm.reset(); panel.hidden = false; await loadSaved(); }
      catch (_) { showStatusError("N\u00e3o foi poss\u00edvel salvar esta consulta."); }
    });
    const renameDialog = page.querySelector("[data-rename-dialog]"), renameForm = page.querySelector("[data-rename-form]");
    page.querySelector("[data-rename-close]").addEventListener("click", () => renameDialog.close());
    panel.addEventListener("click", async event => {
      const open = event.target.closest("[data-open]"), remove = event.target.closest("[data-delete]"), rename = event.target.closest("[data-rename]");
      try {
        if (open) {
          const { views } = await post(page.dataset.savedUrl, { action: "list" }), saved = views.find(view => String(view.id) === open.dataset.open);
          if (!saved) return;
          queryState = normalizeState({ ...cloneDefaults(), ...saved.configuration, filters: { ...cloneDefaults().filters, ...(saved.configuration.filters || {}) } });
          monthExplicitlySelected = Boolean(queryState.selected_month);
          activePreset = null; syncForm(); panel.hidden = true; refresh();
        } else if (remove) { await post(page.dataset.savedUrl, { action: "delete", id: remove.dataset.delete }); await loadSaved(); }
        else if (rename) { renameForm.elements.id.value = rename.dataset.rename; renameForm.elements.name.value = rename.dataset.name; renameDialog.showModal(); renameForm.elements.name.focus(); }
      } catch (_) { showStatusError("N\u00e3o foi poss\u00edvel atualizar suas consultas salvas."); }
    });
    renameForm.addEventListener("submit", async event => {
      event.preventDefault();
      try { await post(page.dataset.savedUrl, { action: "rename", id: renameForm.elements.id.value, name: renameForm.elements.name.value }); renameDialog.close(); await loadSaved(); }
      catch (_) { showStatusError("N\u00e3o foi poss\u00edvel renomear esta consulta."); }
    });
  }
  function showStatusError(message) { page.querySelector("[data-status]").textContent = message; }
  async function exportCurrent(format) {
    const button = page.querySelector(`[data-export="${format}"]`); button.disabled = true;
    const labels = { pdf: "PDF", csv: "CSV", xlsx: "XLSX" };
    page.querySelector("[data-status]").textContent = `Gerando ${labels[format]}...`;
    let failed = false;
    try {
      const response = await fetch(page.dataset.exportUrl, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRFToken": csrf }, credentials: "same-origin", body: JSON.stringify({ ...queryPayload(), include_all_rows: true, format }) });
      if (!response.ok) { const body = await response.json(); throw new Error(body.error?.message || body.error || "Falha na exporta\u00e7\u00e3o."); }
      const blob = await response.blob(), href = URL.createObjectURL(blob), link = document.createElement("a");
      link.href = href; link.download = response.headers.get("content-disposition")?.match(/filename="?([^";]+)"?/i)?.[1] || `arion-cockpit.${format}`;
      document.body.append(link); link.click(); link.remove(); URL.revokeObjectURL(href);
    } catch (_) { failed = true; showStatusError("N\u00e3o foi poss\u00edvel exportar esta an\u00e1lise."); }
    finally { button.disabled = false; if (!failed) page.querySelector("[data-status]").textContent = ""; }
  }
  function clearFilters() { controller?.abort(); temporaryTicketDay = ""; monthExplicitlySelected = false; queryState = cloneDefaults(); activePreset = null; page.querySelector("[data-more-filters]").open = false; syncForm(); refresh(); }

  form.addEventListener("change", () => { readForm(); queryState.detail_page = 1; queryState.ticket_page = 1; syncForm(); updatePresetStatus(); renderActive(); });
  form.addEventListener("submit", event => { event.preventDefault(); temporaryTicketDay = ""; readForm(); queryState.detail_page = 1; queryState.ticket_page = 1; syncForm(); updatePresetStatus(); refresh(); });
  page.querySelector("[data-clear]").addEventListener("click", clearFilters);
  page.querySelector("[data-retry]").addEventListener("click", refresh);
  page.querySelector("[data-breakdown]").addEventListener("change", event => { temporaryTicketDay = ""; queryState.group_by = event.target.value; queryState.detail_page = 1; queryState.ticket_page = 1; updatePresetStatus(); refresh(); });
  page.querySelector("[data-month-select]").addEventListener("change", event => { queryState.selected_month = event.target.value; monthExplicitlySelected = true; refresh(); });
  page.querySelectorAll("[data-quick]").forEach(button => button.addEventListener("click", () => { temporaryTicketDay = ""; presetState(button.dataset.quick); }));
  const dayDialog = page.querySelector("[data-day-dialog]");
  page.querySelector("[data-day-close]").addEventListener("click", () => dayDialog.close());
  page.querySelector("[data-day-view]").addEventListener("click", () => {
    if (!selectedDayForDialog) return;
    temporaryTicketDay = selectedDayForDialog.date; queryState.ticket_page = 1;
    dayDialog.close(); setDetailCollapsed("tickets", false); refresh();
    const ticketsSection = page.querySelector('[data-detail-section="tickets"]');
    const behavior = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
    window.setTimeout(() => ticketsSection.scrollIntoView({ behavior, block: "start" }), 190);
  });
  page.querySelector("[data-day-apply]").addEventListener("click", () => {
    if (!selectedDayForDialog) return;
    temporaryTicketDay = ""; queryState.start = selectedDayForDialog.date; queryState.end = selectedDayForDialog.date;
    queryState.selected_month = selectedDayForDialog.date.slice(0, 7); monthExplicitlySelected = true; queryState.ticket_page = 1; queryState.ticket_search = "";
    syncForm(); dayDialog.close(); refresh();
  });
  page.querySelector("[data-ticket-day-clear]").addEventListener("click", () => {
    temporaryTicketDay = ""; queryState.ticket_page = 1; queryState.ticket_search = ""; refresh();
  });
  page.addEventListener("click", event => {
    const monthPoint = event.target.closest("[data-chart-month]"), calendarDay = event.target.closest("[data-calendar-day]");
    if (monthPoint) { queryState.selected_month = monthPoint.dataset.chartMonth; monthExplicitlySelected = true; refresh(); return; }
    if (calendarDay) {
      selectedDayForDialog = { date: calendarDay.dataset.calendarDay, value: Number(calendarDay.dataset.dayValue || 0) };
      page.querySelector("[data-day-title]").textContent = dateLabel(selectedDayForDialog.date);
      const unit = page.dataset.calendarUnit || "tickets";
      page.querySelector("[data-day-count]").textContent = `${number.format(selectedDayForDialog.value)} ${unit} na consulta atual.`;
      dayDialog.showModal(); return;
    }
    const pageButton = event.target.closest("[data-detail-page]"), drill = event.target.closest("[data-drill]");
    if (pageButton) { queryState.detail_page = Number(pageButton.dataset.detailPage) || 1; refresh(); return; }
    const ticket = event.target.closest("[data-ticket-open]");
    if (ticket) { openTicket(ticket.dataset.ticketOpen); return; }
    const ticketPage = event.target.closest("[data-ticket-page]");
    if (ticketPage) { queryState.ticket_page = Number(ticketPage.dataset.ticketPage) || 1; refresh(); return; }
    if (drill) {
      temporaryTicketDay = "";
      const key = queryState.group_by;
      if (FILTER_KEYS.includes(key)) queryState.filters[key] = drill.dataset.drill;
      queryState.detail_page = 1; queryState.ticket_page = 1; syncForm(); updatePresetStatus(); refresh();
    }
  });
  let ticketSearchTimer;
  page.querySelector("[data-ticket-search]").addEventListener("input", event => {
    clearTimeout(ticketSearchTimer); ticketSearchTimer = setTimeout(() => { queryState.ticket_search = event.target.value.trim().slice(0, 120); queryState.ticket_page = 1; refresh(); }, 300);
  });
  page.querySelector("[data-ticket-size]").addEventListener("change", event => { queryState.ticket_page_size = Number(event.target.value) || 25; queryState.ticket_page = 1; refresh(); });
  const drawer = page.querySelector("[data-ticket-drawer]");
  drawer.querySelector("[data-drawer-close]").addEventListener("click", () => drawer.close());
  page.addEventListener("pointerover", event => { const point = event.target.closest("[data-chart-point]"); if (point) point.dataset.tooltipOpen = "true"; });
  page.addEventListener("pointerout", event => { const point = event.target.closest("[data-chart-point]"); if (point && !point.contains(event.relatedTarget) && point.dataset.tooltipPinned !== "true") delete point.dataset.tooltipOpen; });
  page.addEventListener("focusin", event => { const point = event.target.closest("[data-chart-point]"); if (point) point.dataset.tooltipOpen = "true"; });
  page.addEventListener("focusout", event => { const point = event.target.closest("[data-chart-point]"); if (point && !point.contains(event.relatedTarget) && point.dataset.tooltipPinned !== "true") delete point.dataset.tooltipOpen; });
  page.addEventListener("click", event => {
    if (event.target.closest("[data-chart-month], [data-calendar-day]")) return;
    const point = event.target.closest("[data-chart-point]");
    page.querySelectorAll("[data-chart-point][data-tooltip-pinned='true']").forEach(item => { if (item !== point) { delete item.dataset.tooltipPinned; delete item.dataset.tooltipOpen; } });
    if (point) { const pinned = point.dataset.tooltipPinned === "true"; point.dataset.tooltipPinned = String(!pinned); point.dataset.tooltipOpen = String(!pinned); }
  });
  const exportOptions = page.querySelector("[data-export-options]"), exportToggle = page.querySelector("[data-export-toggle]");
  exportToggle.addEventListener("click", () => { exportOptions.hidden = !exportOptions.hidden; exportToggle.setAttribute("aria-expanded", String(!exportOptions.hidden)); });
  exportOptions.addEventListener("click", event => { const button = event.target.closest("[data-export]"); if (button) { exportOptions.hidden = true; exportToggle.setAttribute("aria-expanded", "false"); exportCurrent(button.dataset.export); } });
  window.addEventListener("popstate", () => { queryState = readURLState(); monthExplicitlySelected = Boolean(queryState.selected_month); activePreset = null; syncForm(); refresh(); });

  syncForm(); initDetailCollapses(); initSavedViews(); refresh();
})();
