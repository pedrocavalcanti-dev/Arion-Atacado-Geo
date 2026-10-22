(() => {
  const drawer = document.querySelector("[data-link-drawer]");
  const backdrop = document.querySelector("[data-drawer-backdrop]");
  const content = document.querySelector("[data-drawer-content]");
  const escape = value => String(value ?? "").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
  const value = (label, text, wide = false) => `<div${wide ? ' class="wide"' : ""}><span>${escape(label)}</span><b>${escape(text || "Não informado")}</b></div>`;
  function closeDrawer() {
    if (!drawer) return;
    drawer.classList.remove("is-open");
    drawer.setAttribute("aria-hidden", "true");
    drawer.inert = true;
    backdrop.hidden = true;
  }
  function renderLink(link) {
    const changeHtml = link.changes.length ? link.changes.map(change => `<div class="drawer-change"><small>${escape(change.created_at)}</small><p><b>${escape(change.field)}</b>: ${escape(change.old || "—")} → ${escape(change.new || "—")}</p></div>`).join("") : '<p class="value-muted">Sem alterações registradas.</p>';
    content.innerHTML = `<header class="drawer-heading"><h2>${escape(link.designation_arion || "Sem designação")}</h2><p>OTRS ConfigItem #${escape(link.config_item_id)} · Versão ${escape(link.version || "—")}</p><span class="source-badge"><i></i>${escape(link.operadora || "Não classificado")} / ${escape(link.projeto || "Não classificado")}</span><span class="state-badge">${escape(link.deployment_state || "Não informado")}</span></header>
      <section class="drawer-section"><h3>Localização</h3><div class="drawer-fields">${value("Endereço", link.address, true)}${value("Cidade", link.city)}${value("UF", link.uf)}</div></section>
      <section class="drawer-section"><h3>Serviço</h3><div class="drawer-fields">${value("Provedor", link.provider)}${value("ConfigItem do provedor", link.provider_cmdb_config_item_id)}${value("ISP original", link.isp_raw, true)}${value("Velocidade", link.speed_raw)}${value("Tipo", link.link_type)}${value("Range IP", link.range_ip)}${value("Circuito", link.circuit)}${value("Designação da operadora", link.operator_designation, true)}</div></section>
      <section class="drawer-section"><h3>Cliente / contrato</h3><div class="drawer-fields">${value("Nome original", link.name, true)}${value("Cliente", link.client_raw)}${value("Contrato", link.contract_number)}${value("Identificação", link.client_identification)}${value("CNPJ ARION", link.cnpj_arion)}${value("Horário", link.business_hours)}</div></section>
      <section class="drawer-section"><h3>Estado no CMDB</h3><div class="drawer-fields">${value("Implantação", link.deployment_state)}${value("Incidente", link.incident_state)}${value("Classificação", link.classification_status)}${value("Versão", link.version)}</div></section>
      <section class="drawer-section"><h3>Observação</h3><div class="drawer-fields">${value("Observação do CMDB", link.notes, true)}</div></section>
      <section class="drawer-section"><h3>Histórico</h3>${changeHtml}</section>`;
  }
  async function openDrawer(id) {
    if (!drawer) return;
    drawer.classList.add("is-open");
    drawer.setAttribute("aria-hidden", "false");
    drawer.inert = false;
    backdrop.hidden = false;
    content.innerHTML = '<p class="drawer-loading">Carregando detalhes…</p>';
    try {
      const response = await fetch(`/base/api/${encodeURIComponent(id)}/`, { headers: { "X-Requested-With": "XMLHttpRequest" } });
      if (!response.ok) throw new Error("Não foi possível carregar os detalhes do link.");
      renderLink(await response.json());
    } catch (error) {
      content.innerHTML = `<p class="drawer-loading">${escape(error.message)}</p>`;
    }
  }
  document.querySelectorAll("[data-link-id]").forEach(row => {
    row.addEventListener("click", () => openDrawer(row.dataset.linkId));
    row.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openDrawer(row.dataset.linkId); }
    });
  });
  document.querySelector("[data-drawer-close]")?.addEventListener("click", closeDrawer);
  backdrop?.addEventListener("click", closeDrawer);
  document.addEventListener("keydown", event => { if (event.key === "Escape") closeDrawer(); });

  document.querySelector("[data-page-size]")?.addEventListener("change", event => {
    const url = new URL(window.location.href);
    url.searchParams.set("page_size", event.target.value);
    url.searchParams.delete("page");
    window.location.href = url;
  });
  const fileInput = document.querySelector('.file-picker input[type="file"]');
  fileInput?.addEventListener("change", () => {
    const name = document.querySelector("[data-file-name]");
    if (name && fileInput.files.length) name.textContent = fileInput.files[0].name;
  });
})();
