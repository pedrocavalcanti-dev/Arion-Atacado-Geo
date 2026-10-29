(() => {
  "use strict";

  const surfaces = [...document.querySelectorAll("[data-spreadsheet]")];

  const storagePrefix = `arion-relatorios:${window.location.pathname}:`;
  const saveState = (key, value) => {
    try { window.localStorage.setItem(storagePrefix + key, JSON.stringify(value)); } catch (_) { /* storage may be disabled */ }
  };
  const readState = (key, fallback) => {
    try { return JSON.parse(window.localStorage.getItem(storagePrefix + key)) ?? fallback; } catch (_) { return fallback; }
  };

  function updateTreatmentCounters(counters) {
    if (!counters) return;
    document.querySelectorAll("[data-count-key]").forEach((node) => {
      const value = counters[node.dataset.countKey];
      if (value !== undefined) node.textContent = String(value);
    });
  }

  const columnKeys = (surface) => [...new Set([...surface.querySelectorAll("[data-column-key]")]
    .map((item) => item.dataset.columnKey).filter(Boolean))];

  function setColumnVisible(surface, key, visible) {
    const frozen = surface.dataset.spreadsheetKind !== "treatment"
      ? surface.querySelector(`[data-column-key="${CSS.escape(key)}"][data-sticky-role]`)
      : null;
    if (frozen) visible = true;
    surface.querySelectorAll(`[data-column-key="${CSS.escape(key)}"]`).forEach((cell) => { cell.hidden = !visible; });
    surface.querySelectorAll(`[data-column-toggle="${CSS.escape(key)}"]`).forEach((input) => { input.checked = visible; });
    updateGroupHeaders(surface);
  }

  function updateGroupHeaders(surface) {
    const table = surface.querySelector(".treatment-grid");
    if (!table) return;
    const groupKeys = {
      identification: ["rec", "designation", "client", "uf", "lp", "ticket", "isp", "provider", "contract", "bandwidth"],
      claro: ["claro-opening", "claro-fetec", "claro-duration", "claro-ev", "monthly", "claro-inter", "claro-penalty", "claro-indisp", "hours"],
      arion: ["arion-opening", "arion-fetec", "pauses", "tmp", "ev", "inter", "indisp", "cause", "procedence", "observation"],
      result: ["total-claro", "total-arion", "contested", "reduction", "decision", "status"],
    };
    Object.entries(groupKeys).forEach(([group, keys]) => {
      const count = keys.filter((key) => {
        const input = surface.querySelector(`[data-column-toggle="${CSS.escape(key)}"]`);
        return !input || input.checked;
      }).length;
      const header = table.querySelector(`.grid-group-row [data-group="${group}"]`);
      if (header) { header.colSpan = Math.max(1, count); header.hidden = count === 0; }
    });
  }

  function applyColumnPreset(surface, preset) {
    const keys = columnKeys(surface);
    const presets = {
      essential: new Set(["rec", "designation", "ticket", "isp", "claro-opening", "claro-fetec", "claro-duration", "claro-ev", "claro-inter", "claro-indisp", "arion-opening", "arion-fetec", "tmp", "ev", "inter", "indisp", "cause", "total-claro", "total-arion", "decision"]),
      claro: new Set(["rec", "designation", "ticket", "claro-opening", "claro-fetec", "claro-duration", "claro-ev", "claro-inter", "claro-indisp", "total-claro", "decision"]),
      arion: new Set(["rec", "designation", "ticket", "arion-opening", "arion-fetec", "tmp", "ev", "inter", "indisp", "isp", "cause", "total-arion", "decision"]),
      finance: new Set(["rec", "designation", "total-claro", "total-arion", "contested", "reduction", "decision"]),
      all: new Set(keys),
    };
    const selected = presets[preset] || presets.all;
    keys.forEach((key) => setColumnVisible(surface, key, selected.has(key)));
    const kind = surface.dataset.spreadsheetKind || "grid";
    saveState(kind === "treatment" ? "columns:treatment:v3" : `columns:${kind}`, [...selected]);
  }

  function applyVisibility(surface, selected) {
    const visible = new Set(selected);
    columnKeys(surface).forEach((key) => setColumnVisible(surface, key, visible.has(key)));
  }

  function applyWidths(surface, widths) {
    const table = surface.querySelector(".spreadsheet-grid");
    if (!table) return;
    Object.entries(widths).forEach(([key, width]) => {
      const numeric = Math.min(520, Math.max(64, Number(width) || 0));
      if (!numeric) return;
      table.querySelectorAll(`[data-column-key="${CSS.escape(key)}"]`).forEach((cell) => {
        cell.style.width = `${numeric}px`;
        cell.style.minWidth = `${numeric}px`;
        cell.style.maxWidth = `${numeric}px`;
      });
      const rec = table.querySelector(`[data-column-key="${CSS.escape(key)}"][data-sticky-role="rec"]`);
      const sourceRow = table.querySelector(`[data-column-key="${CSS.escape(key)}"][data-sticky-role="source-row"]`);
      if (sourceRow && surface.dataset.spreadsheetKind === "original") {
        surface.style.setProperty("--reports-source-row-width", `${numeric}px`);
      }
      if (rec) {
        if (surface.dataset.spreadsheetKind === "original") {
          surface.style.setProperty("--reports-source-rec-width", `${numeric}px`);
        } else {
          surface.style.setProperty("--reports-col-rec-width", `${numeric}px`);
        }
      }
    });
  }

  function setupHorizontalScroll(surface) {
    const proxy = surface.querySelector("[data-horizontal-scroll-proxy]");
    const scrollArea = surface.querySelector(".spreadsheet-grid-scroll");
    const table = surface.querySelector(".spreadsheet-grid");
    const spacer = proxy?.firstElementChild;
    if (!proxy || !scrollArea || !table || !spacer) return;
    let syncing = false;
    const update = () => {
      spacer.style.width = `${Math.max(table.scrollWidth, scrollArea.clientWidth)}px`;
      const hasOverflow = table.scrollWidth > scrollArea.clientWidth + 1;
      proxy.hidden = !hasOverflow;
      if (hasOverflow) proxy.scrollLeft = scrollArea.scrollLeft;
    };
    proxy.addEventListener("scroll", () => {
      if (syncing) return;
      syncing = true;
      scrollArea.scrollLeft = proxy.scrollLeft;
      syncing = false;
    }, { passive: true });
    scrollArea.addEventListener("scroll", () => {
      if (syncing) return;
      syncing = true;
      proxy.scrollLeft = scrollArea.scrollLeft;
      syncing = false;
    }, { passive: true });
    if ("ResizeObserver" in window) {
      const observer = new ResizeObserver(update);
      observer.observe(table);
      observer.observe(scrollArea);
    }
    surface.querySelectorAll("[data-column-toggle]").forEach((input) => input.addEventListener("change", () => requestAnimationFrame(update)));
    window.addEventListener("resize", update, { passive: true });
    update();
  }

  function setupFormulaPopover(surface) {
    const table = surface.querySelector(".treatment-grid");
    if (!table) return;
    const formulas = {
      tmp: "TMP bruto: FETEC OTRS \u2212 Abertura OTRS. TMP efetivo: datas ARION efetivas \u2212 pausas",
      ev: "EV calculado sobre o TMP bruto; EV efetivo usa o TMP efetivo conforme a regra da compet\u00eancia",
      inter: "Inter ARION = (3 \u00d7 Valor mensal Claro \u00d7 EV efetivo) \u00f7 1440",
      unavailability: "Indisp calculada: faixa SLA aplicada ao TMP bruto. Indisp efetiva: faixa SLA aplicada ao TMP efetivo.",
      total: "Total ARION = Inter efetivo + Indisp efetivo + Penal efetiva + valor n\u00e3o cobrado",
    };
    let popover = null;
    const close = () => { popover?.remove(); popover = null; };
    const show = (cell) => {
      close();
      const value = cell.querySelector("[data-value-display]")?.textContent?.trim() || "\u2014";
      const override = cell.querySelector(".override-marker");
      popover = document.createElement("div");
      popover.className = "spreadsheet-formula-popover";
      popover.setAttribute("role", "tooltip");
      const heading = document.createElement("strong");
      heading.textContent = cell.dataset.label || "Valor calculado";
      const description = document.createElement("span");
      description.textContent = `${formulas[cell.dataset.formulaKey] || "Valor calculado pela regra da compet\u00eancia"} \u00b7 Exibido: ${value}${override?.title ? ` \u00b7 ${override.title}` : ""}`;
      popover.append(heading, description);
      surface.append(popover);
      const rect = cell.getBoundingClientRect();
      const left = Math.min(window.innerWidth - popover.offsetWidth - 12, Math.max(12, rect.left));
      const top = rect.bottom + popover.offsetHeight + 12 < window.innerHeight
        ? rect.bottom + 7 : Math.max(12, rect.top - popover.offsetHeight - 7);
      popover.style.left = `${left}px`;
      popover.style.top = `${top}px`;
    };
    table.addEventListener("click", (event) => {
      const cell = event.target.closest("[data-formula-key]");
      if (!cell) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      show(cell);
    });
    table.addEventListener("keydown", (event) => {
      const cell = event.target.closest("[data-formula-key]");
      if (!cell || !["Enter", " "].includes(event.key)) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      show(cell);
    });
    document.addEventListener("click", (event) => { if (popover && !popover.contains(event.target) && !event.target.closest("[data-formula-key]")) close(); });
    document.addEventListener("keydown", (event) => { if (event.key === "Escape") close(); });
  }

  function setupReportPopovers() {
    const menus = [...document.querySelectorAll(".grid-column-menu, .more-treatment-filters")];
    const closeMenu = (menu) => {
      window.clearTimeout(menu._closeTimer);
      menu._closeTimer = null;
      menu.open = false;
    };
    const closeOthers = (active) => menus.forEach((menu) => { if (menu !== active) closeMenu(menu); });
    menus.forEach((menu) => {
      menu.addEventListener("toggle", () => { if (menu.open) closeOthers(menu); });
      menu.addEventListener("pointerenter", () => { window.clearTimeout(menu._closeTimer); menu._closeTimer = null; });
      menu.addEventListener("pointerleave", () => {
        if (!menu.open) return;
        menu._closeTimer = window.setTimeout(() => closeMenu(menu), 2000);
      });
    });
    document.addEventListener("click", (event) => {
      if (!event.target.closest(".grid-column-menu, .more-treatment-filters")) menus.forEach(closeMenu);
    });
    document.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return;
      const active = menus.find((menu) => menu.open);
      if (active) { closeMenu(active); active.querySelector("summary")?.focus(); }
    });
  }

  setupReportPopovers();

  function enableResize(surface) {
    const table = surface.querySelector(".spreadsheet-grid");
    if (!table) return;
    const widthStateKey = `widths:${surface.dataset.spreadsheetKind || "grid"}`;
    const widths = readState(widthStateKey, {});
    applyWidths(surface, widths);
    const headers = [...table.querySelectorAll("thead th[data-column-key]")];
    headers.forEach((header) => {
      if (header.rowSpan > 1 && header.dataset.columnKey === "actions") return;
      const handle = document.createElement("span");
      handle.className = "column-resizer";
      handle.setAttribute("role", "separator");
      handle.setAttribute("aria-orientation", "vertical");
      handle.setAttribute("aria-label", `Redimensionar coluna ${header.textContent.trim()}`);
      handle.tabIndex = 0;
      header.append(handle);
      handle.addEventListener("pointerdown", (event) => {
        event.preventDefault();
        const key = header.dataset.columnKey;
        const startX = event.clientX;
        const startWidth = header.getBoundingClientRect().width;
        handle.setPointerCapture?.(event.pointerId);
        const move = (moveEvent) => {
          const width = Math.min(520, Math.max(64, startWidth + moveEvent.clientX - startX));
          widths[key] = Math.round(width);
          applyWidths(surface, widths);
        };
        const finish = () => {
          handle.removeEventListener("pointermove", move);
          handle.removeEventListener("pointerup", finish);
          saveState(widthStateKey, widths);
        };
        handle.addEventListener("pointermove", move);
        handle.addEventListener("pointerup", finish, { once: true });
      });
      handle.addEventListener("keydown", (event) => {
        if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
        event.preventDefault();
        const key = header.dataset.columnKey;
        const current = widths[key] || Math.round(header.getBoundingClientRect().width);
        widths[key] = Math.min(520, Math.max(64, current + (event.key === "ArrowRight" ? 12 : -12)));
        applyWidths(surface, widths);
        saveState(widthStateKey, widths);
      });
    });
  }

  let fallbackFullscreen = null;
  function enterFullscreen(surface) {
    if (fallbackFullscreen) {
      fallbackFullscreen.classList.remove("is-fullscreen");
      const wasActive = fallbackFullscreen === surface;
      fallbackFullscreen = null;
      document.body.classList.remove("reports-fullscreen");
      if (wasActive) { syncFullscreenButtons(); return; }
    }
    if (document.fullscreenElement) {
      document.exitFullscreen?.().catch?.(() => {});
      return;
    }
    if (surface.requestFullscreen) {
      surface.requestFullscreen().catch(() => {
        fallbackFullscreen = surface;
        surface.classList.add("is-fullscreen");
        document.body.classList.add("reports-fullscreen");
        syncFullscreenButtons();
      });
    } else {
      fallbackFullscreen = surface;
      surface.classList.add("is-fullscreen");
      document.body.classList.add("reports-fullscreen");
      syncFullscreenButtons();
    }
  }

  function syncFullscreenButtons() {
    const active = document.fullscreenElement || fallbackFullscreen;
    surfaces.forEach((surface) => surface.querySelectorAll("[data-fullscreen-toggle]").forEach((button) => {
      const selected = active === surface;
      const label = button.querySelector("[data-fullscreen-label]");
      if (label) label.textContent = selected ? "Sair da tela cheia" : "Tela cheia";
      else button.textContent = selected ? "Sair da tela cheia" : "Tela cheia";
      button.setAttribute("aria-label", selected ? "Sair da tela cheia" : "Abrir planilha em tela cheia");
    }));
    if (!active) document.body.classList.remove("reports-fullscreen");
  }

  document.addEventListener("fullscreenchange", syncFullscreenButtons);
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (fallbackFullscreen) {
      fallbackFullscreen.classList.remove("is-fullscreen");
      fallbackFullscreen = null;
      syncFullscreenButtons();
    } else if (document.fullscreenElement) {
      event.preventDefault();
      document.exitFullscreen?.().catch?.(() => {});
    }
  });

  const formatValue = (value, key = "") => {
    if (value === null || value === undefined || value === "") return "—";
    if (key === "events") {
      const parsed = Number(String(value).trim().replace(",", "."));
      if (Number.isFinite(parsed)) return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(parsed);
    }
    if (key === "ev") {
      const raw = String(value).trim();
      const parsed = Number(raw.includes(",") ? raw.replace(/\./g, "").replace(",", ".") : raw);
      if (Number.isFinite(parsed)) return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(parsed);
    }
    if (/(monthly_value|_fine)$/.test(key)) {
      const raw = String(value).trim();
      const parsed = Number(raw.includes(",") ? raw.replace(/\./g, "").replace(",", ".") : raw);
      if (Number.isFinite(parsed)) return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(parsed);
    }
    if (/(opening|fetec)$/.test(key) && typeof value === "string") {
      const date = new Date(value);
      if (!Number.isNaN(date.getTime())) return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(date);
    }
    return String(value);
  };

  function section(title, entries) {
    const wrapper = document.createElement("section");
    wrapper.className = "drawer-section";
    const heading = document.createElement("h3");
    heading.textContent = title;
    wrapper.append(heading);
    const list = document.createElement("dl");
    list.className = "drawer-data-grid";
    entries.forEach(([label, value]) => {
      const pair = document.createElement("div");
      const term = document.createElement("dt");
      const description = document.createElement("dd");
      term.textContent = label;
      description.textContent = value === null || value === undefined || value === "" ? "—" : String(value);
      pair.append(term, description);
      list.append(pair);
    });
    wrapper.append(list);
    return wrapper;
  }

  function listSection(title, items, renderItem) {
    const wrapper = document.createElement("section");
    wrapper.className = "drawer-section";
    const heading = document.createElement("h3");
    heading.textContent = title;
    wrapper.append(heading);
    const list = document.createElement("ul");
    list.className = "drawer-list";
    if (!items?.length) {
      const item = document.createElement("li");
      item.textContent = "Nenhum registro.";
      list.append(item);
    } else items.forEach((data) => {
      const item = document.createElement("li");
      item.textContent = renderItem(data);
      list.append(item);
    });
    wrapper.append(list);
    return wrapper;
  }

  function renderDrawer(data, content, table) {
    const drawer = content.closest("[data-treatment-drawer]");
    const footer = drawer?.querySelector("[data-drawer-footer]");
    content.replaceChildren();
    footer?.replaceChildren();
    const safeText = (value) => value === null || value === undefined || value === "" ? "—" : String(value);
    const label = (parent, text, name, value, type = "text", options = null) => {
      const wrapper = document.createElement("label");
      wrapper.className = "drawer-field";
      wrapper.textContent = text;
      let input;
      if (options) {
        input = document.createElement("select");
        input.className = "reports-select";
        options.forEach(([code, title]) => {
          const option = document.createElement("option");
          option.value = code;
          option.textContent = title;
          input.append(option);
        });
      } else if (type === "textarea") {
        input = document.createElement("textarea");
        input.rows = 2;
      } else {
        input = document.createElement("input");
        input.type = type;
      }
      input.name = name;
      input.value = value ?? "";
      input.classList.add("reports-input");
      wrapper.append(input);
      parent.append(wrapper);
      return input;
    };
    const details = (title, child) => {
      const element = document.createElement("details");
      element.className = "drawer-advanced";
      const summary = document.createElement("summary");
      summary.textContent = title;
      element.append(summary, child);
      return element;
    };
    const heading = document.createElement("div");
    heading.className = "drawer-case-heading";
    const subtitle = drawer?.querySelector("#treatment-drawer-meta");
    if (subtitle) subtitle.textContent = `${safeText(data.claro?.client)} · ${safeText(data.claro?.uf)}`;

    content.append(section("Claro · somente leitura", [
      ["Abertura", formatValue(data.claro?.opening, "opening")],
      ["FETEC", formatValue(data.claro?.fetec, "fetec")],
      ["Tempo", formatValue(data.claro?.duration, "duration")],
      ["EV", formatValue(data.claro?.events, "events")],
      ["Inter", formatValue(data.claro?.interconnection_fine, "interconnection_fine")],
      ["Indisp.", formatValue(data.claro?.unavailability_fine, "unavailability_fine")],
      ["Total", data.totals?.claro],
    ]));

    const ticketSection = document.createElement("section");
    ticketSection.className = "drawer-section drawer-section--tickets";
    const ticketHeading = document.createElement("h3");
    ticketHeading.textContent = "Ticket principal · PU Fornecedor";
    ticketSection.append(ticketHeading);
    const tickets = data.evidence?.tickets || [];
    const match = data.evidence?.ticket_match || {};
    const primary = tickets.find((item) => item.is_primary) || tickets[0];
    if (primary) {
      const identity = document.createElement("div");
      identity.className = "drawer-primary-ticket";
      const link = document.createElement("a");
      link.className = "drawer-ticket-link";
      link.textContent = `${primary.number} ↗`;
      if (primary.url) { link.href = primary.url; link.target = "_blank"; link.rel = "noopener noreferrer"; }
      else link.setAttribute("aria-disabled", "true");
      const state = document.createElement("small");
      state.textContent = [primary.status, primary.queue, primary.responsible ? `Responsável ID ${primary.responsible}` : ""].filter(Boolean).join(" · ");
      identity.append(link, state);
      const method = document.createElement("small");
      method.className = "drawer-match-method";
      const matchLabels = {
        EXACT_PU: "Encontrado pelo PU exato",
        PU_PREFIX_REC_LP: "PU arredondado confirmado por REC/CI + LP",
        REC_CI_LP: "Encontrado por REC/CI + LP",
        PU_PREFIX_REC_CI: "PU arredondado confirmado por REC/CI",
        PU_PREFIX_LP: "PU arredondado confirmado por LP",
        MANUAL: "Ticket confirmado manualmente",
      };
      const confidenceLabel = match.confidence === "HIGH" ? "Confiança alta"
        : match.confidence === "MEDIUM" ? "Confiança média"
          : match.confidence === "USER_CONFIRMED" ? "Confiança confirmada pelo usuário" : "";
      method.textContent = [matchLabels[match.method] || "Ticket relacionado", confidenceLabel].filter(Boolean).join(" · ");
      identity.append(method);
      ticketSection.append(identity);
      const evidenceGrid = document.createElement("dl");
      evidenceGrid.className = "drawer-data-grid";
      [["Abertura OTRS · automática", data.arion?.opening_auto], ["FETEC OTRS · automática", data.arion?.fetec_auto],
        ["ISP", data.arion?.isp], ["Nome completo", data.arion?.isp_full_name], ["Origem do ISP", data.origins?.isp],
        ["ConfigItemID da operadora", data.arion?.isp_config_item_id || data.arion?.isp_internal_id], ["Number da operadora", data.arion?.isp_provider_number],
        ["Procedência", data.arion?.procedence], ["Origem da procedência", data.origins?.procedence]].forEach(([name, value]) => {
        const pair = document.createElement("div"); const term = document.createElement("dt"); const description = document.createElement("dd");
        term.textContent = name; description.textContent = safeText(value); pair.append(term, description); evidenceGrid.append(pair);
      });
      ticketSection.append(evidenceGrid);
    } else {
      const missing = document.createElement("p");
      missing.className = "drawer-warning";
      const number = data.evidence?.pu_received || data.evidence?.ticket_identifier || "não informado";
      missing.textContent = data.evidence?.lookup_error
        ? `${data.evidence.lookup_error} A Tratativa continua disponível manualmente.`
        : data.evidence?.status_code === "AMBIGUOUS"
        ? `PU recebido: ${number} · REC: ${safeText(data.evidence?.rec)} · LP: ${safeText(data.evidence?.lp)}. Não foi possível confirmar um único ticket no mirror local.`
        : !data.evidence?.ticket_identifier
        ? "PU Fornecedor não contém um número de ticket válido."
        : data.evidence.status_code === "NOT_CHECKED"
          ? `PU Fornecedor: ${number}. A busca no mirror local ainda não foi executada.`
          : `PU recebido: ${number} · REC: ${safeText(data.evidence?.rec)} · LP: ${safeText(data.evidence?.lp)}. Nenhum ticket compatível foi encontrado no mirror OTRS local.`;
      ticketSection.append(missing);
    }
    const candidates = data.evidence?.ticket_candidates || [];
    if (candidates.length && match.confidence === "AMBIGUOUS") {
      const candidateForm = document.createElement("form");
      candidateForm.className = "drawer-ticket-candidate-form";
      candidateForm.dataset.ticketCandidateForm = "";
      const candidateHeading = document.createElement("p");
      candidateHeading.className = "drawer-match-method";
      candidateHeading.textContent = `Encontramos ${candidates.length} possível(is) ticket(s). Selecione o correto.`;
      candidateForm.append(candidateHeading);
      const candidateList = document.createElement("ul");
      candidateList.className = "drawer-ticket-candidates";
      candidates.forEach((candidate) => {
        const item = document.createElement("li");
        const option = document.createElement("label");
        const radio = document.createElement("input");
        radio.type = "radio"; radio.name = "ticket_number"; radio.value = candidate.number; radio.required = true;
        const detailsNode = document.createElement("span");
        const numberNode = document.createElement("strong"); numberNode.textContent = candidate.number;
        const evidenceNode = document.createElement("small");
        const ci = candidate.matched_ci?.length ? candidate.matched_ci : candidate.ci || [];
        const lp = candidate.matched_lp?.length ? candidate.matched_lp : candidate.lp || [];
        evidenceNode.textContent = [`CI ${ci.join(", ") || "sem correspondência"}`, `LP ${lp.join(", ") || "sem correspondência"}`, candidate.status_label || candidate.status, candidate.queue].filter(Boolean).join(" · ");
        detailsNode.append(numberNode, evidenceNode);
        option.append(radio, detailsNode); item.append(option); candidateList.append(item);
      });
      candidateForm.append(candidateList);
      const chooseButton = document.createElement("button");
      chooseButton.type = "submit"; chooseButton.className = "reports-button reports-button--primary";
      chooseButton.textContent = "Vincular selecionado"; chooseButton.disabled = true;
      candidateForm.addEventListener("change", () => { chooseButton.disabled = !candidateForm.querySelector('input[name="ticket_number"]:checked'); });
      const feedback = document.createElement("span"); feedback.className = "drawer-ticket-feedback"; feedback.setAttribute("role", "status");
      candidateForm.append(chooseButton, feedback);
      ticketSection.append(candidateForm);
    }
    if (tickets.length > 1) {
      const allTickets = document.createElement("ul");
      allTickets.className = "drawer-ticket-list";
      tickets.forEach((ticket) => {
        const item = document.createElement("li");
        const line = document.createElement("div"); line.className = "drawer-ticket-identity";
        const ticketLink = document.createElement("a"); ticketLink.className = "drawer-ticket-link"; ticketLink.textContent = ticket.number;
        if (ticket.url) { ticketLink.href = ticket.url; ticketLink.target = "_blank"; ticketLink.rel = "noopener noreferrer"; }
        else ticketLink.setAttribute("aria-disabled", "true");
        const role = document.createElement("small"); role.textContent = ticket.source_code === "AUTOMATIC" ? "Principal · PU Fornecedor" : ticket.is_primary ? "Ticket principal manual" : "Relacionado manualmente";
        line.append(ticketLink, role); item.append(line);
        const meta = document.createElement("small");
        meta.textContent = [ticket.status, ticket.queue, ticket.title, ticket.opened_at !== "—" ? `Abertura ${ticket.opened_at}` : "", ticket.resolved_at !== "—" ? `FETEC ${ticket.resolved_at}` : ""].filter(Boolean).join(" · ");
        item.append(meta);
        if (ticket.config_items?.length) {
          const configItems = document.createElement("small");
          configItems.textContent = `Itens de configuração: ${ticket.config_items.map((item) => `${item.name}${item.isp ? ` · ISP ${item.isp}` : ""}${item.isp_internal_id ? ` · ConfigItemID operadora ${item.isp_internal_id}` : ""}${item.isp_provider_number ? ` · Number operadora ${item.isp_provider_number}` : ""}`).join(", ")}`;
          item.append(configItems);
        }
        allTickets.append(item);
      });
      ticketSection.append(details(`Tickets relacionados (${tickets.length})`, allTickets));
    }
    let result = null;
    if (data.permissions?.can_edit) {
      const ticketForm = document.createElement("form"); ticketForm.className = "drawer-ticket-form"; ticketForm.dataset.ticketLinkForm = "";
      const ticketInput = label(ticketForm, "Vincular outro ticket", "ticket_number", "", "text");
      ticketInput.maxLength = 80; ticketInput.placeholder = "Número exato do ticket OTRS"; ticketInput.autocomplete = "off";
      const ticketSubmit = document.createElement("button"); ticketSubmit.type = "submit"; ticketSubmit.className = "reports-button"; ticketSubmit.textContent = "+ Vincular outro ticket";
      const feedback = document.createElement("span"); feedback.className = "drawer-ticket-feedback"; feedback.setAttribute("role", "status");
      ticketForm.append(ticketSubmit, feedback); ticketSection.append(ticketForm);
    }
    if (data.evidence?.isp_candidates?.length > 1) {
      const warning = document.createElement("p"); warning.className = "drawer-warning";
      warning.textContent = `ISP não definido automaticamente; candidatos no mirror CMDB: ${data.evidence.isp_candidates.join(", ")}.`;
      ticketSection.append(warning);
    }
    if (data.evidence?.procedence_candidates?.length > 1) {
      const warning = document.createElement("p"); warning.className = "drawer-warning";
      warning.textContent = `Procedência não definida automaticamente; evidências OTRS divergentes: ${data.evidence.procedence_candidates.join(", ")}.`;
      ticketSection.append(warning);
    }
    content.append(ticketSection);

    const totals = data.totals || {};
    content.append(section("Tempo ARION", [
      ["TMP calculado / bruto", totals.tmp_gross === null ? "—" : `${totals.tmp_gross} min`],
      ["Pausas", `${totals.pause_minutes || 0} min`],
      ["TMP efetivo ARION", totals.tmp_effective === null ? "—" : `${totals.tmp_effective} min`],
      ["EV", `${formatValue(data.calculations?.ev?.calculated, "ev")} calculado · ${formatValue(data.calculations?.ev?.effective, "ev")} efetivo`],
    ]));
    const pauseSection = data.permissions?.can_edit ? document.createElement("section") : null;
    if (pauseSection) {
      pauseSection.className = "drawer-section drawer-pause-section";
      const pauseHeading = document.createElement("h3"); pauseHeading.textContent = "Pausas"; pauseSection.append(pauseHeading);
      const pauseTotal = document.createElement("p"); pauseTotal.className = "drawer-pause-total"; pauseTotal.textContent = `Total: ${totals.pause_minutes || 0} min`; pauseSection.append(pauseTotal);
      const pauseList = document.createElement("ul"); pauseList.className = "drawer-list";
      (data.pauses || []).forEach((pause) => {
        const item = document.createElement("li");
        item.textContent = `${pause.duration} min · ${pause.kind} · ${pause.reason} · Evidência: ${pause.evidence || "—"} · ${pause.created_at} · ${pause.user}`;
        pauseList.append(item);
      });
      if (data.pauses?.length) pauseSection.append(pauseList);
      const pauseForm = document.createElement("form"); pauseForm.className = "drawer-pause-form"; pauseForm.action = data.form?.pause_url; pauseForm.dataset.drawerPauseForm = "";
      const pauseVersion = document.createElement("input"); pauseVersion.type = "hidden"; pauseVersion.name = "version"; pauseVersion.value = String(data.version); pauseForm.append(pauseVersion);
      const kind = label(pauseForm, "Tipo", "kind", "MINUTES", "select", [["MINUTES", "Minutos"], ["INTERVAL", "Intervalo"]]);
      const minutes = label(pauseForm, "Minutos", "minutes", "", "number"); minutes.min = "1"; minutes.required = true;
      const interval = document.createElement("div"); interval.className = "drawer-form-grid";
      label(interval, "Início", "started_at", "", "datetime-local"); label(interval, "Fim", "ended_at", "", "datetime-local");
      pauseForm.append(details("Mais opções de intervalo", interval));
      label(pauseForm, "Motivo", "reason", "").required = true;
      label(pauseForm, "Evidência / observação", "evidence", "").required = true;
      const pauseSubmit = document.createElement("button"); pauseSubmit.type = "submit"; pauseSubmit.className = "reports-button"; pauseSubmit.textContent = "+ Adicionar pausa";
      const pauseFeedback = document.createElement("span"); pauseFeedback.className = "drawer-form-feedback"; pauseFeedback.setAttribute("role", "status");
      pauseForm.append(pauseSubmit, pauseFeedback); pauseSection.append(pauseForm);
      kind.addEventListener("change", () => {
        minutes.disabled = kind.value !== "MINUTES";
        minutes.required = kind.value === "MINUTES";
      });
      content.append(pauseSection);
    }
    const comparison = document.createElement("section");
    comparison.className = "drawer-section drawer-comparison";
    const comparisonHeading = document.createElement("h3"); comparisonHeading.textContent = "Comparação Claro · ARION";
    const comparisonTable = document.createElement("table");
    comparisonTable.innerHTML = "<thead><tr><th></th><th>Claro</th><th>ARION</th></tr></thead><tbody></tbody>";
    const comparisonRows = [
      ["EV", formatValue(data.claro?.events, "events"), formatValue(data.calculations?.ev?.effective, "ev")],
      ["Inter", formatValue(data.claro?.interconnection_fine, "interconnection_fine"), formatValue(data.calculations?.inter?.effective, "inter")],
      ["Indisp.", formatValue(data.claro?.unavailability_fine, "unavailability_fine"), formatValue(data.calculations?.unavailability?.effective, "unavailability")],
    ];
    comparisonRows.forEach(([name, claroValue, arionValue]) => {
      const row = document.createElement("tr");
      [name, claroValue, arionValue].forEach((value, index) => { const cell = document.createElement(index === 0 ? "th" : "td"); cell.textContent = value; row.append(cell); });
      comparisonTable.tBodies[0].append(row);
    });
    comparison.append(comparisonHeading, comparisonTable);
    content.append(comparison);

    if (data.permissions?.can_edit) {
      const treatmentForm = document.createElement("form");
      treatmentForm.id = `drawer-treatment-form-${data.id}`;
      treatmentForm.className = "drawer-treatment-form";
      treatmentForm.action = data.form?.edit_url || data.edit_url;
      treatmentForm.dataset.drawerTreatmentForm = "";
      const version = document.createElement("input"); version.type = "hidden"; version.name = "version"; version.value = String(data.version); treatmentForm.append(version);
      const fieldGrid = document.createElement("div"); fieldGrid.className = "drawer-form-grid";
      label(fieldGrid, `Abertura efetiva · origem ${data.origins?.opening || "—"} · OTRS ${data.arion?.opening_auto || "—"}`, "arion_opening_at", data.arion?.opening_input, "datetime-local");
      label(fieldGrid, `FETEC efetiva · origem ${data.origins?.fetec || "—"} · OTRS ${data.arion?.fetec_auto || "—"}`, "arion_fetec_at", data.arion?.fetec_input, "datetime-local");
      const ispInput = label(fieldGrid, "ISP", "isp", data.arion?.isp === "ISP não identificado" || data.arion?.isp === "—" ? "" : data.arion?.isp);
      if (data.arion?.isp_internal_id && data.arion?.isp === "ISP não identificado") ispInput.placeholder = `ID interno CMDB ${data.arion.isp_internal_id} · informe um nome`;
      label(fieldGrid, "Procedência", "procedence", data.arion?.procedence_code, "select", [["UNSPECIFIED", "Não informada"], ["PROCEDENT", "Procedente"], ["IMPROCEDENT", "Improcedente"]]);
      label(fieldGrid, "Causa raiz", "root_cause", data.arion?.root_cause === "—" ? "" : data.arion?.root_cause);
      label(fieldGrid, "Status", "status", data.arion?.status_code, "select", [["PENDING", "Pendente"], ["IN_ANALYSIS", "Em análise"], ["TREATED", "Tratado"], ["REVIEW", "Em revisão"], ["APPROVED", "Aprovado"]]);
      treatmentForm.append(fieldGrid);
      label(treatmentForm, "Observação", "observation", data.arion?.observation === "—" ? "" : data.arion?.observation, "textarea");
      label(treatmentForm, "Justificativa da tratativa", "treatment_justification", data.arion?.treatment_justification, "text");

      result = document.createElement("section"); result.className = "drawer-result-section";
      const resultHeading = document.createElement("h3"); resultHeading.textContent = "Resultado"; result.append(resultHeading);
      const resultGrid = document.createElement("div"); resultGrid.className = "drawer-result-grid";
      [["Claro", totals.claro], ["ARION", totals.arion], ["Contestado", totals.contested], ["Redução", totals.reduction]].forEach(([name, value]) => {
        const metric = document.createElement("div"); const nameNode = document.createElement("small"); const valueNode = document.createElement("strong");
        nameNode.textContent = name; valueNode.textContent = safeText(value); metric.append(nameNode, valueNode); resultGrid.append(metric);
      });
      result.append(resultGrid);
      label(treatmentForm, "Decisão", "decision", data.arion?.decision_code, "select", [["PENDING", "Pendente de análise"], ["DUE", "Cobrança devida"], ["REDUCED", "Cobrança reduzida"], ["INVALID", "Cobrança indevida"], ["REVIEW", "Revisar"]]);
      label(treatmentForm, "Motivo da decisão", "decision_reason", data.arion?.decision_reason);

      const financialDetails = document.createElement("div"); financialDetails.className = "drawer-advanced-fields";
      label(financialDetails, "Valor não cobrado", "amount_not_charged", data.arion?.amount_not_charged || "0", "number");
      label(financialDetails, "Justificativa do valor não cobrado", "amount_not_charged_justification", data.arion?.amount_not_charged_justification);
      const secretStatus = document.createElement("p"); secretStatus.className = "reports-muted";
      secretStatus.textContent = `Senhas de validação: ${data.validation_codes?.first_configured ? "Senha 1 configurada" : "Senha 1 não configurada"} · ${data.validation_codes?.second_configured ? "Senha 2 configurada" : "Senha 2 não configurada"}. Os valores não são exibidos.`;
      financialDetails.append(secretStatus);
      label(financialDetails, "Senha de validação", "validation_code", "", "password");
      label(financialDetails, "Senha de validação 02", "validation_code_2", "", "password");
      const clearCodes = document.createElement("div"); clearCodes.className = "drawer-form-grid";
      label(clearCodes, "Remover senha de validação", "clear_validation_code", "", "checkbox");
      label(clearCodes, "Remover senha de validação 02", "clear_validation_code_2", "", "checkbox");
      financialDetails.append(clearCodes);
      treatmentForm.append(details("Valores adicionais e senhas", financialDetails));
      content.append(treatmentForm);
    } else {
      content.append(section("Tratativa ARION", [
        ["Abertura", data.arion?.opening], ["FETEC", data.arion?.fetec], ["ISP", data.arion?.isp],
        ["Causa raiz", data.arion?.root_cause], ["Procedência", data.arion?.procedence], ["Decisão", data.arion?.decision],
      ]));
    }

    const calculations = document.createElement("section"); calculations.className = "drawer-section drawer-calculations";
    const calcHeading = document.createElement("h3"); calcHeading.textContent = "Valores calculados e efetivos"; calculations.append(calcHeading);
    const calcGrid = document.createElement("dl"); calcGrid.className = "drawer-data-grid";
    const calcLabels = { tmp: "TMP ARION · min", ev: "EV ARION", inter: "Inter ARION", unavailability: "Indisp. ARION" };
    Object.entries(calcLabels).forEach(([key, title]) => {
      const item = data.calculations?.[key] || {};
      const pair = document.createElement("div"); const term = document.createElement("dt"); const description = document.createElement("dd");
      term.textContent = title;
      description.textContent = `Calculado: ${formatValue(item.calculated, key)} · Efetivo: ${formatValue(item.effective, key)}`;
      pair.append(term, description); calcGrid.append(pair);
    });
    calculations.append(calcGrid);
    if (data.permissions?.can_override) {
      const overrideForm = document.createElement("form"); overrideForm.className = "drawer-override-form"; overrideForm.dataset.drawerOverrideForm = "";
      overrideForm.action = data.form?.override_url;
      const versionInput = document.createElement("input"); versionInput.type = "hidden"; versionInput.name = "version"; versionInput.value = String(data.version); overrideForm.append(versionInput);
      const overrideFields = document.createElement("div"); overrideFields.className = "drawer-form-grid";
      label(overrideFields, "Campo", "field", "ev", "select", [["tmp", "TMP ARION"], ["ev", "EV ARION"], ["inter", "Inter ARION"], ["unavailability", "Indisp. ARION"], ["penalty", "Penal ARION"]]);
      label(overrideFields, "Novo valor", "value", "", "number");
      label(overrideFields, "Justificativa", "justification", ""); overrideForm.append(overrideFields);
      const submit = document.createElement("button"); submit.type = "submit"; submit.className = "reports-button"; submit.textContent = "Aplicar ajuste"; overrideForm.append(submit);
      calculations.append(details("Alterar valor calculado", overrideForm));
    }
    content.append(details("Cálculos e opções avançadas", calculations));
    if (result) content.append(result);

    const advanced = document.createElement("div"); advanced.className = "drawer-advanced-stack";
    if (tickets.length && data.permissions?.can_edit) {
      const ticketActions = document.createElement("div"); ticketActions.className = "drawer-ticket-list drawer-ticket-actions-list";
      const hasPuPrimary = tickets.some((ticket) => ticket.source_code === "AUTOMATIC");
      tickets.forEach((ticket) => {
        if (ticket.is_primary || !ticket.relation_id) return;
        const actions = document.createElement("div"); actions.className = "drawer-ticket-actions";
        if (!hasPuPrimary) {
          const makePrimary = document.createElement("button"); makePrimary.type = "button"; makePrimary.className = "reports-button"; makePrimary.textContent = "Tornar principal";
          makePrimary.dataset.ticketAction = "primary"; makePrimary.dataset.relationId = String(ticket.relation_id); actions.append(makePrimary);
        }
        const unlink = document.createElement("button"); unlink.type = "button"; unlink.className = "reports-button"; unlink.textContent = "Desvincular";
        unlink.dataset.ticketAction = "unlink"; unlink.dataset.relationId = String(ticket.relation_id); actions.append(unlink);
        ticketActions.append(actions);
      });
      if (ticketActions.childElementCount) advanced.append(details("Gerenciar tickets relacionados", ticketActions));
    }
    const sourceLabels = { ENRICHMENT: "Enriquecimento", INLINE_EDIT: "Edição na planilha", MANUAL_EDIT: "Edição manual", PAUSE_ADDED: "Pausa adicionada", PAUSE_REMOVED: "Pausa removida", OVERRIDE_APPLIED: "Ajuste aplicado", OVERRIDE_REMOVED: "Ajuste removido", TREATMENT: "Tratativa" };
    advanced.append(listSection("Histórico financeiro", data.history, (item) => `${item.created_at} · ${item.user} · ${sourceLabels[item.source] || "Alteração"} · ${item.previous ?? "—"} → ${item.new ?? "—"}`));
    const fallback = document.createElement("a"); fallback.className = "drawer-link"; fallback.href = data.edit_url; fallback.textContent = "Abrir edição completa";
    advanced.append(details("Mais detalhes", fallback));
    if (data.permissions?.can_edit) {
      const enrich = document.createElement("button"); enrich.type = "button"; enrich.className = "reports-button drawer-enrich-button";
      enrich.textContent = "Buscar evidências do ticket"; enrich.dataset.enrichTreatment = ""; advanced.append(enrich);
    }
    content.append(details("Histórico e opções avançadas", advanced));

    if (footer) {
      const navigation = document.createElement("nav"); navigation.className = "drawer-case-navigation"; navigation.setAttribute("aria-label", "Navegação entre casos filtrados");
      const previous = document.createElement("button"); previous.type = "button"; previous.className = "reports-button"; previous.textContent = "← Anterior";
      previous.dataset.navigateTreatment = data.navigation.previous_id || ""; previous.disabled = !data.navigation.previous_id;
      const position = document.createElement("span"); position.textContent = `Caso ${data.navigation.position} de ${data.navigation.count}`;
      const next = document.createElement("button"); next.type = "button"; next.className = "reports-button"; next.textContent = "Próximo →";
      next.dataset.navigateTreatment = data.navigation.next_id || ""; next.disabled = !data.navigation.next_id;
      navigation.append(previous, position, next); footer.append(navigation);
      if (data.permissions?.can_edit) {
        const actions = document.createElement("div"); actions.className = "drawer-footer-actions";
        const save = document.createElement("button"); save.type = "submit"; save.className = "reports-button"; save.textContent = "Salvar";
        save.setAttribute("form", `drawer-treatment-form-${data.id}`); save.dataset.drawerSubmitAction = "save";
        const saveNext = document.createElement("button"); saveNext.type = "submit"; saveNext.className = "reports-button reports-button--primary"; saveNext.textContent = "Salvar e próximo pendente";
        saveNext.setAttribute("form", `drawer-treatment-form-${data.id}`); saveNext.dataset.drawerSubmitAction = "next";
        actions.append(save, saveNext); footer.append(actions);
      }
      const feedback = document.createElement("p"); feedback.className = "drawer-save-feedback"; feedback.dataset.drawerFeedback = ""; feedback.setAttribute("role", "status"); footer.append(feedback);
    }

    const row = table.querySelector(`[data-treatment-id="${CSS.escape(String(data.id))}"]`);
    if (row && data.grid) {
      row.dataset.version = String(data.version);
      const values = {
        isp: data.grid.isp, "arion-opening": data.grid.opening, "arion-fetec": data.grid.fetec, pauses: data.grid.pauses,
        tmp: data.grid.tmp, ev: data.grid.ev, inter: data.grid.inter, indisp: data.grid.indisp, cause: data.grid.cause,
        observation: data.grid.observation, procedence: data.grid.procedence, "total-claro": data.grid.total_claro,
        "total-arion": data.grid.total_arion, contested: data.grid.contested, reduction: data.grid.reduction,
        decision: data.grid.decision, status: data.grid.status, ticket: data.grid.ticket,
      };
      Object.entries(values).forEach(([key, value]) => {
        const cell = row.querySelector(`[data-column-key="${CSS.escape(key)}"]`);
        if (!cell) return;
        if (key === "ticket") {
          cell.replaceChildren();
          if (data.grid.ticket_url) {
            const link = document.createElement("a");
            link.href = data.grid.ticket_url;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            link.textContent = safeText(value);
            cell.append(link);
          } else {
            const marker = document.createElement("span");
            marker.className = `evidence-marker evidence-marker--${data.grid.ticket_state}`;
            marker.textContent = safeText(value);
            cell.append(marker);
          }
          return;
        }
        const target = cell.querySelector("[data-value-display], .decision-badge, .evidence-marker, [data-start-edit]");
        if (target) target.textContent = safeText(value);
        else cell.firstChild && cell.firstChild.nodeType === Node.TEXT_NODE ? cell.firstChild.textContent = safeText(value) : cell.prepend(document.createTextNode(safeText(value)));
        if (key === "decision") {
          row.dataset.decision = data.grid.decision_code.toLowerCase();
          const badge = cell.querySelector(".decision-badge");
          if (badge) badge.className = `decision-badge decision-badge--${data.grid.decision_code.toLowerCase()}`;
        }
      });
      const titleValues = {
        isp: data.grid.isp_title, tmp: data.grid.tmp_title, ev: data.grid.ev_title,
        inter: data.grid.inter_title, indisp: data.grid.indisp_title,
      };
      Object.entries(titleValues).forEach(([key, value]) => {
        const cell = row.querySelector(`[data-column-key="${CSS.escape(key)}"]`);
        if (cell && value) cell.title = value;
      });
      const editableValues = { isp: data.arion?.isp === "—" ? "" : data.arion?.isp, "arion-opening": data.arion?.opening_input, "arion-fetec": data.arion?.fetec_input, cause: data.arion?.root_cause === "—" ? "" : data.arion?.root_cause, observation: data.arion?.observation === "—" ? "" : data.arion?.observation, procedence: data.arion?.procedence_code, decision: data.arion?.decision_code };
      Object.entries(editableValues).forEach(([key, value]) => { const cell = row.querySelector(`[data-column-key="${CSS.escape(key)}"]`); if (cell && value !== undefined) cell.dataset.value = value; });
    }
  }

  function setupDrawer(surface) {
    const table = surface.querySelector(".treatment-grid");
    const drawer = surface.querySelector("[data-treatment-drawer]");
    const content = drawer?.querySelector("[data-drawer-content]");
    const title = drawer?.querySelector("#treatment-drawer-title");
    if (!table || !drawer || !content) return;
    let previousFocus = null;
    let activeId = null;
    let activeRow = null;
    let activeData = null;
    let activeController = null;
    let successNotice = "";
    const close = () => {
      activeController?.abort();
      activeData = null;
      activeId = null;
      drawer.hidden = true;
      drawer.querySelector("[data-drawer-footer]")?.replaceChildren();
      table.querySelectorAll("tr.is-selected").forEach((row) => row.classList.remove("is-selected"));
      previousFocus?.focus?.();
    };
    drawer.querySelectorAll("[data-close-drawer]").forEach((button) => button.addEventListener("click", close));
    const endpointFor = (id) => {
      const template = table.dataset.detailEndpointTemplate?.replace("/0/", `/${id}/`);
      if (!template) return null;
      const endpoint = new URL(template, window.location.href);
      const query = new URLSearchParams(table.dataset.detailQuery || "");
      query.forEach((value, key) => endpoint.searchParams.set(key, value));
      return endpoint.toString();
    };
    const open = async (rowOrId, preserveFocus = false) => {
      const row = typeof rowOrId === "string" || typeof rowOrId === "number"
        ? table.querySelector(`[data-treatment-id="${CSS.escape(String(rowOrId))}"]`)
        : rowOrId;
      const treatmentId = row?.dataset.treatmentId || String(rowOrId || "");
      if (!treatmentId) return;
      const endpoint = endpointFor(treatmentId);
      if (!endpoint) return;
      if (!preserveFocus) previousFocus = document.activeElement;
      table.querySelectorAll("tr.is-selected").forEach((item) => item.classList.remove("is-selected"));
      row?.classList.add("is-selected");
      activeId = treatmentId;
      activeRow = row || null;
      activeData = null;
      activeController?.abort();
      const controller = new AbortController();
      activeController = controller;
      drawer.hidden = false;
      content.replaceChildren();
      drawer.querySelector("[data-drawer-footer]")?.replaceChildren();
      const loading = document.createElement("p");
      loading.textContent = "Carregando evidências dos mirrors locais…";
      content.append(loading);
      drawer.setAttribute("aria-busy", "true");
      drawer.querySelector(".drawer-close")?.focus();
      try {
        const response = await fetch(endpoint, {
          headers: { Accept: "application/json", "X-Requested-With": "XMLHttpRequest" },
          credentials: "same-origin", cache: "no-store", mode: "same-origin", signal: controller.signal,
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        if (!response.headers.get("content-type")?.includes("application/json")) throw new Error("A resposta do servidor não é JSON.");
        const data = await response.json();
        if (controller.signal.aborted || activeId !== treatmentId) return;
        activeData = data;
        title.textContent = `${data.rec} · ${data.designation}`;
        renderDrawer(data, content, table);
        if (successNotice) {
          const feedback = drawer.querySelector("[data-drawer-feedback]");
          if (feedback) feedback.textContent = successNotice;
          successNotice = "";
        }
      } catch (error) {
        if (error.name === "AbortError") return;
        console.warn("Falha ao buscar detalhes da tratativa", { treatmentId, endpoint, error });
        content.replaceChildren();
        const message = document.createElement("p");
        message.className = "drawer-load-error";
        message.setAttribute("role", "alert");
        message.textContent = "Não foi possível carregar os detalhes desta linha.";
        const retry = document.createElement("button");
        retry.className = "reports-button";
        retry.type = "button";
        retry.textContent = "Tentar novamente";
        retry.dataset.retryDrawer = "";
        content.append(message, retry);
      } finally {
        if (activeId === treatmentId) drawer.removeAttribute("aria-busy");
      }
    };
    const postJson = async (url, values) => {
      const csrf = document.querySelector("[name=csrfmiddlewaretoken]")?.value || "";
      const body = new URLSearchParams({ ...values, csrfmiddlewaretoken: csrf });
      const response = await fetch(url, {
        method: "POST", body, credentials: "same-origin", cache: "no-store",
        headers: { "X-Requested-With": "XMLHttpRequest", Accept: "application/json", "X-CSRFToken": csrf },
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || !result.ok) throw new Error(result.error || `HTTP ${response.status}`);
      return result;
    };
    drawer.addEventListener("submit", async (event) => {
      const form = event.target.closest("[data-drawer-treatment-form], [data-drawer-pause-form], [data-drawer-override-form], [data-ticket-link-form], [data-ticket-candidate-form]");
      if (!form || !activeData) return;
      event.preventDefault();
      const submitter = event.submitter;
      const button = submitter || form.querySelector("button[type=submit]");
      const formFeedback = form.querySelector("[role=status]");
      const footerFeedback = drawer.querySelector("[data-drawer-feedback]");
      if (button) button.disabled = true;
      if (formFeedback) formFeedback.textContent = "Salvando…";
      if (footerFeedback) footerFeedback.textContent = "Salvando…";
      try {
        const values = Object.fromEntries(new FormData(form).entries());
        let endpoint;
        if (form.matches("[data-ticket-link-form]")) {
          endpoint = activeData.ticket_relation_url;
          values.action = "link";
        } else if (form.matches("[data-ticket-candidate-form]")) {
          endpoint = activeData.ticket_relation_url;
          values.action = "candidate";
        } else if (form.matches("[data-drawer-pause-form]")) endpoint = activeData.form.pause_url;
        else if (form.matches("[data-drawer-override-form]")) endpoint = activeData.form.override_url;
        else {
          endpoint = new URL(form.action, window.location.href);
          new URLSearchParams(table.dataset.detailQuery || "").forEach((value, key) => endpoint.searchParams.set(key, value));
          if (submitter?.dataset.drawerSubmitAction === "next") values.save_and_next = "1";
        }
        const result = await postJson(endpoint, values);
        const savedId = activeId;
        updateTreatmentCounters(result.counters);
        successNotice = result.message || (form.matches("[data-ticket-link-form], [data-ticket-candidate-form]") ? "Ticket vinculado." : form.matches("[data-drawer-pause-form]") ? "Pausa adicionada; TMP recalculado." : form.matches("[data-drawer-override-form]") ? "Ajuste aplicado." : "Tratativa salva.");
        await open(savedId, true);
        if (form.matches("[data-drawer-treatment-form]") && result.next_id) {
          successNotice = "Caso salvo. Abrindo o próximo pendente…";
          await open(result.next_id, true);
        }
      } catch (error) {
        console.warn("Falha ao salvar dados da tratativa", { treatmentId: activeId, error });
        if (formFeedback) formFeedback.textContent = error.message || "Não foi possível salvar os dados.";
        if (footerFeedback) footerFeedback.textContent = error.message || "Não foi possível salvar os dados.";
        if (button) button.disabled = false;
      }
    });
    drawer.addEventListener("click", async (event) => {
      const ticketAction = event.target.closest("[data-ticket-action]");
      const navigate = event.target.closest("[data-navigate-treatment]");
      const retry = event.target.closest("[data-retry-drawer]");
      const enrich = event.target.closest("[data-enrich-treatment]");
      if (retry) { open(activeId, true); return; }
      if (navigate?.dataset.navigateTreatment) { open(navigate.dataset.navigateTreatment, true); return; }
      if (ticketAction && activeData) {
        ticketAction.disabled = true;
        try {
          await postJson(activeData.ticket_relation_url, { action: ticketAction.dataset.ticketAction, relation_id: ticketAction.dataset.relationId });
          await open(activeId, true);
        } catch (error) {
          console.warn("Falha ao atualizar vínculo de ticket", { treatmentId: activeId, error });
          ticketAction.disabled = false;
          ticketAction.title = error.message;
        }
      }
      if (enrich && activeData) {
        enrich.disabled = true;
        enrich.textContent = "Procurando no mirror local…";
        const remoteStatus = window.setTimeout(() => {
          if (enrich.isConnected) enrich.textContent = "Consultando OTRS em modo somente leitura…";
        }, 350);
        try {
          await postJson(activeData.enrich_url, {});
          window.clearTimeout(remoteStatus);
          await open(activeId, true);
        } catch (error) {
          window.clearTimeout(remoteStatus);
          console.warn("Falha ao atualizar evidências da linha", { treatmentId: activeId, error });
          enrich.disabled = false;
          enrich.textContent = error.message || "Tentar novamente";
        }
      }
    });
    table.addEventListener("click", (event) => {
      if (event.target.closest("a, button, input, select, textarea")) return;
      const row = event.target.closest("[data-treatment-row]");
      if (row) open(row);
    });
    table.addEventListener("keydown", (event) => {
      const row = event.target.closest("[data-treatment-row]");
      if (!row || event.target.closest("a, button, input, select, textarea")) return;
      if (!["Enter", " "].includes(event.key)) return;
      event.preventDefault();
      open(row);
    });
    drawer.addEventListener("keydown", (event) => { if (event.key === "Escape") close(); });
    return { open, close };
  }

  surfaces.forEach((surface) => {
    const kind = surface.dataset.spreadsheetKind || "grid";
    const columnsStateKey = kind === "treatment" ? "columns:treatment:v3" : `columns:${kind}`;
    const savedColumns = readState(columnsStateKey, null);
    if (savedColumns) applyVisibility(surface, savedColumns);
    else if (kind === "treatment") applyVisibility(surface, [
      "rec", "designation", "ticket", "isp",
      "claro-opening", "claro-fetec", "claro-duration", "claro-ev", "claro-inter", "claro-indisp",
      "arion-opening", "arion-fetec", "tmp", "ev", "inter", "indisp", "cause",
      "total-claro", "total-arion", "decision",
    ]);
    const density = readState(`density:${kind}`, "compact");
    surface.dataset.density = density;
    surface.querySelectorAll("[data-density]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.density === density)));
    surface.querySelectorAll("[data-column-toggle]").forEach((input) => input.addEventListener("change", () => {
      setColumnVisible(surface, input.dataset.columnToggle, input.checked);
       saveState(columnsStateKey, columnKeys(surface).filter((key) => {
        const toggle = surface.querySelector(`[data-column-toggle="${CSS.escape(key)}"]`);
        return toggle ? toggle.checked : !surface.querySelector(`[data-column-key="${CSS.escape(key)}"]`)?.hidden;
      }));
    }));
    surface.querySelectorAll("[data-preset]").forEach((button) => button.addEventListener("click", () => applyColumnPreset(surface, button.dataset.preset)));
    surface.querySelectorAll("[data-columns-all]").forEach((button) => button.addEventListener("click", () => applyColumnPreset(surface, "all")));
    surface.querySelectorAll("[data-density]").forEach((button) => button.addEventListener("click", () => {
      surface.dataset.density = button.dataset.density;
      surface.querySelectorAll("[data-density]").forEach((item) => item.setAttribute("aria-pressed", String(item === button)));
      saveState(`density:${kind}`, button.dataset.density);
    }));
    surface.querySelectorAll("[data-fullscreen-toggle]").forEach((button) => button.addEventListener("click", () => enterFullscreen(surface)));
    enableResize(surface);
    setupHorizontalScroll(surface);
    setupFormulaPopover(surface);
    setupDrawer(surface);
  });

  const deleteDialog = document.querySelector("[data-delete-dialog]");
  const deleteConfirmation = deleteDialog?.querySelector("[data-delete-confirmation]");
  const deleteConfirmationValue = deleteDialog?.querySelector("[data-delete-confirmation-value]")?.dataset.deleteConfirmationValue || "";
  const deleteSubmit = deleteDialog?.querySelector("[data-delete-submit]");
  let fallbackDeleteDialog = false;
  const closeDeleteDialog = () => {
    if (typeof deleteDialog?.close === "function" && deleteDialog.open) deleteDialog.close();
    else deleteDialog?.removeAttribute("open");
    fallbackDeleteDialog = false;
  };
  document.querySelectorAll("[data-open-delete-dialog]").forEach((button) => button.addEventListener("click", () => {
    if (typeof deleteDialog?.showModal === "function") deleteDialog.showModal();
    else { deleteDialog?.setAttribute("open", ""); fallbackDeleteDialog = true; }
    deleteConfirmation?.focus();
  }));
  document.querySelectorAll("[data-close-delete-dialog]").forEach((button) => button.addEventListener("click", closeDeleteDialog));
  deleteConfirmation?.addEventListener("input", () => {
    if (deleteSubmit) deleteSubmit.disabled = deleteConfirmation.value.trim().toUpperCase() !== deleteConfirmationValue.toUpperCase();
  });
  deleteDialog?.addEventListener("click", (event) => {
    if (event.target === deleteDialog) closeDeleteDialog();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && fallbackDeleteDialog) closeDeleteDialog();
  });
})();
