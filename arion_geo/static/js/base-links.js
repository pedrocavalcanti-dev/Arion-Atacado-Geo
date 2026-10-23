(() => {
  const drawer = document.querySelector("[data-link-drawer]");
  const backdrop = document.querySelector("[data-drawer-backdrop]");
  const content = document.querySelector("[data-drawer-content]");
  const escape = value => String(value ?? "").replace(/[&<>\"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
  const value = (label, text, empty = "Não informado", wide = false) => `<div${wide ? ' class="wide"' : ""}><span>${escape(label)}</span><b>${escape(text || empty)}</b></div>`;
  const resolutionLabel = method => ({ CONFIG_ITEM_ID: "ConfigItemID", NAME: "Nome", UNRESOLVED: "Não resolvida", EMPTY: "Sem valor na origem" }[method] || method || "Não informado");

  function closeDrawer() {
    if (!drawer) return;
    drawer.classList.remove("is-open");
    drawer.setAttribute("aria-hidden", "true");
    drawer.inert = true;
    backdrop.hidden = true;
  }

  function section(title, fields) {
    return `<section class="drawer-section"><h3>${escape(title)}</h3><div class="drawer-fields">${fields}</div></section>`;
  }

  function renderLink(link) {
    const incident = link.incident_state || "Não informado";
    content.innerHTML = `<header class="drawer-heading">
        <h2>${escape(link.designation_arion || "Não informado")}</h2>
        <p>Number ${escape(link.config_item_number || "Não informado")} · ConfigItemID ${escape(link.config_item_id)} · Versão ${escape(link.version || "Não informado")}</p>
        <div class="drawer-statuses"><span class="state-badge">Implantação: ${escape(link.deployment_state || "Não informado")}</span><span class="incident-badge${incident.toLowerCase() === "incident" ? " is-incident" : ""}">Incidente: ${escape(incident)}</span></div>
      </header>
      ${section("Relacionamento", value("Projeto legado", link.project_legacy, "Não classificado") + value("Operadora contratada", link.operadora, "Não classificada") + value("Provedor", link.provider, "Não classificado") + value("Number CMDB do provedor", link.provider_cmdb_number) + value("ConfigItemID do provedor", link.provider_cmdb_config_item_id, "Não classificado") + value("ISP original", link.isp_raw) + value("Método de resolução", resolutionLabel(link.provider_resolution_method)))}
      ${section("Localização", value("Endereço", link.address, "Não informado", true) + value("Cidade", link.city) + value("UF", link.uf))}
      ${section("Dados do Link", value("Circuito", link.circuit) + value("Tipo", link.link_type) + value("Velocidade", link.speed_raw) + value("Range IP", link.range_ip, "Não informado", true) + value("Equipamento", link.equipment) + value("MAC Address", link.mac_address) + value("Identificação", link.client_identification) + value("Número do contrato", link.contract_number) + value("CNPJ", link.cnpj_arion) + value("Nome original", link.name, "Não informado", true))}
      ${section("Dados CMDB", value("ConfigItemID do Link", link.config_item_id) + value("Number do Link", link.config_item_number) + value("DefinitionID", link.definition_id) + value("VersionID", link.version) + value("LastVersionID", link.last_version) + value("Último sync", link.synced_at))}
      ${link.notes ? section("Observação CMDB", value("Observação", link.notes, "Não informado", true)) : ""}`;
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
      if (!response.ok) throw new Error("Não foi possível carregar os detalhes do Link.");
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

  document.querySelectorAll("[data-sort-key], [data-page-number]").forEach(link => {
    link.addEventListener("click", event => {
      event.preventDefault();
      const url = new URL(window.location.href);
      if (link.dataset.sortKey) url.searchParams.set("sort", link.dataset.sortKey);
      if (link.dataset.pageNumber) url.searchParams.set("page", link.dataset.pageNumber);
      window.location.href = url;
    });
  });
  document.querySelector("[data-page-size]")?.addEventListener("change", event => {
    const url = new URL(window.location.href);
    url.searchParams.set("page_size", event.target.value);
    url.searchParams.delete("page");
    window.location.href = url;
  });
  const clearSearch = document.querySelector("[data-clear-search]");
  const searchInput = clearSearch?.previousElementSibling;
  searchInput?.addEventListener("input", () => { clearSearch.hidden = !searchInput.value; });
  clearSearch?.addEventListener("click", () => {
    if (!searchInput) return;
    searchInput.value = "";
    clearSearch.hidden = true;
    searchInput.form?.requestSubmit();
  });
})();
