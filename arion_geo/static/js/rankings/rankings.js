(() => {
  const root = document.querySelector("[data-ranking-root]");
  const dataNode = document.getElementById("ranking-page-data");
  if (!root || !dataNode) return;

  const pageItems = JSON.parse(dataNode.textContent);
  const leadersNode = document.getElementById("ranking-top-providers");
  const leaders = leadersNode ? JSON.parse(leadersNode.textContent) : [];
  const drawer = root.querySelector("[data-provider-drawer]");
  const backdrop = root.querySelector("[data-drawer-backdrop]");
  const drawerContent = root.querySelector("[data-drawer-content]");
  const compareToolbar = root.querySelector("[data-compare-toolbar]");
  const compareDialog = root.querySelector("[data-compare-dialog]");
  const compareContent = root.querySelector("[data-compare-content]");
  const formatInteger = new Intl.NumberFormat("pt-BR");
  const formatDecimal = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const months = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out"];
  const selectedIds = new Set();
  let focusedBeforeDrawer = null;
  let currentProviderId = null;

  const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
  const pct = value => `${formatDecimal.format(Number(value) || 0)}%`;
  const real = item => item.real || {};
  const demo = item => item.operational || {};

  function detailUrl(providerId) {
    const template = root.dataset.detailUrlTemplate || "";
    const path = template.replace(/0\/?$/, `${encodeURIComponent(providerId)}/`);
    const url = new URL(path, window.location.origin);
    const current = new URLSearchParams(window.location.search);
    ["period", "operator", "project", "q"].forEach(key => {
      if (current.has(key)) url.searchParams.set(key, current.get(key));
    });
    return url;
  }

  function renderList(title, values, key) {
    const content = values.length
      ? `<ul class="drawer-data-list">${values.map(value => `<li><span>${escapeHtml(value[key])}</span><b>${formatInteger.format(value.links || 0)} ${value.links === 1 ? "link" : "links"}</b></li>`).join("")}</ul>`
      : '<p class="drawer-empty-note">Sem dados classificados na CMDB para este recorte.</p>';
    return `<section class="drawer-section"><header><h3>${title}</h3><small>REAL · CMDB</small></header>${content}</section>`;
  }

  function renderPerformanceMetric(label, value) {
    return `<div class="performance-metric"><span>${label}</span><strong>${value}</strong><small>DEMO</small></div>`;
  }

  function renderDrawer(item) {
    const base = real(item);
    const metrics = demo(item);
    const rankLabel = item.ranking_position ? `${item.ranking_position}º no ranking atual` : "Posição no ranking atual";
    root.querySelector("[data-drawer-rank]").textContent = rankLabel;
    root.querySelector("#drawer-title").textContent = item.name;
    root.querySelector("[data-drawer-meta]").textContent = `${formatInteger.format(base.links || 0)} links · ${pct(base.share)} da CMDB visível`;
    const score = Math.max(0, Math.min(100, Number(metrics.score) || 0));
    const monthlyMax = Math.max(...(metrics.history || [1]), 1);
    const history = (metrics.history || []).map((count, index) => {
      const height = Math.max(8, Math.round((count / monthlyMax) * 100));
      return `<div title="${months[index]}: ${formatInteger.format(count)} chamados demonstrativos"><b>${formatInteger.format(count)}</b><i style="height:${height}%"></i><small>${months[index]}</small></div>`;
    }).join("");
    const baseUrl = new URL(root.dataset.baseUrl || "/base/", window.location.origin);
    baseUrl.searchParams.set("view", "links");
    baseUrl.searchParams.set("provedor", item.name);

    drawerContent.innerHTML = `
      <section class="drawer-overview" aria-label="Resumo do provedor">
        <div><span>Links · REAL</span><strong>${formatInteger.format(base.links || 0)}</strong></div>
        <div><span>Participação · REAL</span><strong>${pct(base.share)}</strong></div>
        <div><span>Projetos · REAL</span><strong>${formatInteger.format((base.projects || []).length)}</strong></div>
        <div><span>UFs · REAL</span><strong>${formatInteger.format((base.states || []).length)}</strong></div>
      </section>
      <section class="drawer-section drawer-cmdb-section"><header><h3>Base CMDB</h3><small>REAL · OTRS / CMDB</small></header>
        <dl class="drawer-cmdb-grid">
          <div><dt>ConfigItem do provedor</dt><dd>${escapeHtml(base.cmdb_config_item_id || "Não informado")}</dd></div>
          <div><dt>Links presentes</dt><dd>${formatInteger.format(base.links || 0)}</dd></div>
          <div><dt>Links classificados</dt><dd>${formatInteger.format(base.classified_links || 0)}</dd></div>
          <div><dt>Links não classificados</dt><dd>${formatInteger.format(base.unclassified_links || 0)}</dd></div>
          <div><dt>Municípios</dt><dd>${formatInteger.format((base.cities || []).length)}</dd></div>
        </dl>
      </section>
      ${renderList("Projetos legados", base.projects || [], "name")}
      ${renderList("Provedores", base.operators || [], "name")}
      ${renderList("Principais UFs", (base.states || []).slice(0, 5), "uf")}
      <section class="drawer-section drawer-demo-section"><header><h3>Performance operacional</h3><small>DEMONSTRAÇÃO · ${escapeHtml(item.operational_source || "DEMO")}</small></header>
        <div class="drawer-score-row"><div class="score-ring score-ring--drawer" role="img" aria-label="Score demonstrativo ${formatDecimal.format(score)} de 100" style="--score:${score}%"><span><strong>${formatDecimal.format(score)}</strong><small>DEMO</small></span></div><p>Indicadores simulados até a integração dos tickets OTRS.</p></div>
        <div class="performance-grid">
          ${renderPerformanceMetric("Chamados", formatInteger.format(metrics.tickets || 0))}
          ${renderPerformanceMetric("SLA atendido", pct(metrics.sla_percent))}
          ${renderPerformanceMetric("Reincidências", `${formatInteger.format(metrics.recurrences || 0)} · ${pct(metrics.recurrence_percent)}`)}
          ${renderPerformanceMetric("Estourados", formatInteger.format(metrics.overdue || 0))}
          ${renderPerformanceMetric("Uptime", pct(metrics.uptime))}
          ${renderPerformanceMetric("Avaliação", `${formatDecimal.format(metrics.rating)} / 5`)}
        </div>
        <h4 class="history-title">Histórico mensal · demonstração</h4>
        <div class="history-legend"><span><i aria-hidden="true"></i>Chamados simulados</span><small>Jan–Out/2026</small></div>
        <div class="history-bars" role="img" aria-label="Histórico mensal demonstrativo de chamados">${history}</div>
      </section>
      <footer class="drawer-actions"><a class="ranking-button ranking-button--primary" href="${escapeHtml(baseUrl.toString())}">Ver links deste provedor <span aria-hidden="true">→</span></a></footer>`;
  }

  async function openDrawer(providerId, trigger) {
    currentProviderId = String(providerId);
    focusedBeforeDrawer = trigger || document.activeElement;
    const summary = pageItems.find(item => String(item.id) === currentProviderId)
      || leaders.find(item => String(item.id) === currentProviderId);
    drawer.hidden = false;
    backdrop.hidden = false;
    document.body.classList.add("drawer-open");
    root.querySelector("#drawer-title").textContent = summary?.name || "Carregando provedor";
    root.querySelector("[data-drawer-rank]").textContent = summary?.ranking_position ? `${summary.ranking_position}º no ranking atual` : "";
    root.querySelector("[data-drawer-meta]").textContent = "Consultando métricas no escopo autorizado…";
    drawerContent.innerHTML = '<p class="drawer-loading" role="status">Carregando análise do provedor…</p>';
    root.querySelector("[data-drawer-close]").focus();
    try {
      const response = await fetch(detailUrl(providerId), { headers: { Accept: "application/json" } });
      const item = await response.json();
      if (!response.ok) throw new Error(item.error?.message || item.error || "Falha ao carregar os dados.");
      if (String(providerId) !== currentProviderId) return;
      if (!item.ranking_position && summary?.ranking_position) item.ranking_position = summary.ranking_position;
      renderDrawer(item);
    } catch (error) {
      if (String(providerId) !== currentProviderId) return;
      drawerContent.innerHTML = `<div class="drawer-error" role="alert"><p>Não foi possível carregar a análise deste provedor.</p><button type="button" class="ranking-button ranking-button--quiet" data-retry-detail="${escapeHtml(providerId)}">Tentar novamente</button></div>`;
    }
  }

  function closeDrawer() {
    drawer.hidden = true;
    backdrop.hidden = true;
    document.body.classList.remove("drawer-open");
    currentProviderId = null;
    if (focusedBeforeDrawer?.isConnected) focusedBeforeDrawer.focus();
  }

  function comparisonRows(items) {
    const rows = [
      ["Links", item => formatInteger.format(real(item).links || 0), "REAL · CMDB"],
      ["Participação", item => pct(real(item).share), "REAL · CMDB"],
      ["Projetos", item => formatInteger.format((real(item).projects || []).length), "REAL · CMDB"],
      ["Provedores", item => formatInteger.format((real(item).operators || []).length), "REAL · CMDB"],
      ["UFs", item => formatInteger.format((real(item).states || []).length), "REAL · CMDB"],
      ["Chamados", item => formatInteger.format(demo(item).tickets || 0), "DEMO"],
      ["SLA atendido", item => pct(demo(item).sla_percent), "DEMO"],
      ["Reincidência", item => `${formatInteger.format(demo(item).recurrences || 0)} · ${pct(demo(item).recurrence_percent)}`, "DEMO"],
      ["Estourados", item => formatInteger.format(demo(item).overdue || 0), "DEMO"],
      ["Score", item => formatDecimal.format(demo(item).score), "DEMO"],
    ];
    return `<div class="compare-table-wrap"><table class="compare-table"><thead><tr><th>Métrica</th>${items.map(item => `<th><span>${escapeHtml(item.name)}</span><small>Provedor</small></th>`).join("")}</tr></thead><tbody>${rows.map(([label, value, source]) => `<tr><th>${label}<small>${source}</small></th>${items.map(item => `<td>${escapeHtml(value(item))}</td>`).join("")}</tr>`).join("")}</tbody></table></div><p class="compare-note">Os indicadores DEMO são demonstrativos; maior quantidade de links não significa melhor desempenho.</p>`;
  }

  function updateCompareToolbar() {
    const count = selectedIds.size;
    compareToolbar.hidden = count === 0;
    root.querySelector("[data-compare-count]").textContent = `${count} ${count === 1 ? "provedor selecionado" : "provedores selecionados"}`;
    root.querySelector("[data-compare-open]").disabled = count < 2;
    root.querySelector("[data-compare-limit]").hidden = true;
  }

  root.addEventListener("click", event => {
    const opener = event.target.closest("[data-open]");
    if (opener) openDrawer(opener.dataset.open, opener);
  });

  root.addEventListener("change", event => {
    const checkbox = event.target.closest("[data-compare]");
    if (!checkbox) return;
    const id = String(checkbox.dataset.compare);
    if (checkbox.checked && selectedIds.size >= 3) {
      checkbox.checked = false;
      root.querySelector("[data-compare-limit]").hidden = false;
      return;
    }
    if (checkbox.checked) selectedIds.add(id);
    else selectedIds.delete(id);
    updateCompareToolbar();
  });

  root.querySelector("[data-compare-clear]").addEventListener("click", () => {
    selectedIds.clear();
    root.querySelectorAll("[data-compare]").forEach(checkbox => { checkbox.checked = false; });
    updateCompareToolbar();
  });

  root.querySelector("[data-compare-open]").addEventListener("click", () => {
    const items = [...selectedIds].map(id => pageItems.find(item => String(item.id) === id)).filter(Boolean);
    if (items.length < 2 || items.length > 3) return;
    compareContent.innerHTML = comparisonRows(items);
    compareDialog.showModal();
  });

  root.querySelector("[data-compare-close]").addEventListener("click", () => compareDialog.close());
  root.querySelector("[data-drawer-close]").addEventListener("click", closeDrawer);
  backdrop.addEventListener("click", closeDrawer);
  drawerContent.addEventListener("click", event => {
    const retry = event.target.closest("[data-retry-detail]");
    if (retry) openDrawer(retry.dataset.retryDetail, retry);
  });

  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && !drawer.hidden) closeDrawer();
    if (event.key !== "Tab" || drawer.hidden) return;
    const focusable = [...drawer.querySelectorAll('button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])')];
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });
})();
