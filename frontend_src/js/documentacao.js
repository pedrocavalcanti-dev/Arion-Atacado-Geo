(() => {
  const shell = document.querySelector("[data-docs-shell]");
  const sidebar = document.querySelector("[data-docs-sidebar]");
  const menuButton = document.querySelector("[data-docs-sidebar-toggle]");
  const scrim = document.querySelector("[data-docs-scrim]");
  const mobileLayout = window.matchMedia("(max-width: 820px)");
  const sidebarStorageKey = "arion-docs-sidebar";
  if (!shell || !sidebar || !menuButton || !scrim) return;

  const isSidebarOpen = () => mobileLayout.matches
    ? document.body.classList.contains("docs-menu-open")
    : !shell.classList.contains("is-sidebar-collapsed");

  const updateSidebarState = ({ focus = false, persist = false } = {}) => {
    const open = isSidebarOpen();
    sidebar.inert = !open;
    sidebar.setAttribute("aria-hidden", String(!open));
    menuButton.setAttribute("aria-expanded", String(open));
    menuButton.setAttribute("aria-label", open
      ? (mobileLayout.matches ? "Fechar navegação documental" : "Recolher navegação documental")
      : (mobileLayout.matches ? "Abrir navegação documental" : "Expandir navegação documental"));
    if (focus && open) sidebar.querySelector("a")?.focus();
    if (focus && !open) menuButton.focus();
    if (persist && !mobileLayout.matches) {
      try { localStorage.setItem(sidebarStorageKey, open ? "open" : "closed"); } catch (_) { /* local preference is optional */ }
    }
  };

  const applyLayout = () => {
    document.body.classList.remove("docs-menu-open");
    if (mobileLayout.matches) {
      shell.classList.remove("is-sidebar-collapsed");
    } else {
      let shouldOpen = true;
      try { shouldOpen = localStorage.getItem(sidebarStorageKey) !== "closed"; } catch (_) { /* use expanded default */ }
      shell.classList.toggle("is-sidebar-collapsed", !shouldOpen);
    }
    updateSidebarState();
  };

  menuButton.addEventListener("click", () => {
    if (mobileLayout.matches) {
      document.body.classList.toggle("docs-menu-open");
      updateSidebarState({ focus: document.body.classList.contains("docs-menu-open") });
      return;
    }
    shell.classList.toggle("is-sidebar-collapsed");
    updateSidebarState({ focus: false, persist: true });
  });

  const closeMobileSidebar = () => {
    if (!mobileLayout.matches || !document.body.classList.contains("docs-menu-open")) return;
    document.body.classList.remove("docs-menu-open");
    updateSidebarState({ focus: true });
  };
  scrim.addEventListener("click", closeMobileSidebar);
  sidebar.querySelectorAll("a").forEach((link) => link.addEventListener("click", closeMobileSidebar));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeMobileSidebar();
  });
  mobileLayout.addEventListener?.("change", applyLayout);
  applyLayout();

  const diagramDialog = document.createElement("dialog");
  diagramDialog.className = "docs-diagram-dialog";
  diagramDialog.setAttribute("aria-label", "Diagrama ampliado");
  const dialogSurface = document.createElement("div");
  dialogSurface.className = "docs-diagram-dialog__surface";
  const dialogHeader = document.createElement("header");
  dialogHeader.className = "docs-diagram-dialog__header";
  const dialogHeading = document.createElement("div");
  const dialogTitle = document.createElement("h2");
  dialogTitle.className = "docs-diagram-dialog__title";
  dialogTitle.textContent = "Diagrama ampliado";
  const dialogHint = document.createElement("p");
  dialogHint.className = "docs-diagram-dialog__hint";
  dialogHint.textContent = "Use a rolagem, o trackpad ou deslize no touch para percorrer o desenho.";
  dialogHeading.append(dialogTitle, dialogHint);
  const dialogControls = document.createElement("div");
  dialogControls.className = "docs-diagram-dialog__controls";
  const zoomOut = document.createElement("button");
  zoomOut.type = "button";
  zoomOut.className = "docs-diagram-dialog__button";
  zoomOut.setAttribute("aria-label", "Diminuir zoom");
  zoomOut.textContent = "−";
  const zoomLabel = document.createElement("span");
  zoomLabel.className = "docs-diagram-dialog__zoom";
  zoomLabel.setAttribute("aria-live", "polite");
  const zoomIn = document.createElement("button");
  zoomIn.type = "button";
  zoomIn.className = "docs-diagram-dialog__button";
  zoomIn.setAttribute("aria-label", "Aumentar zoom");
  zoomIn.textContent = "+";
  const zoomReset = document.createElement("button");
  zoomReset.type = "button";
  zoomReset.className = "docs-diagram-dialog__button";
  zoomReset.setAttribute("aria-label", "Redefinir zoom");
  zoomReset.textContent = "1:1";
  const dialogClose = document.createElement("button");
  dialogClose.type = "button";
  dialogClose.className = "docs-diagram-dialog__button docs-diagram-dialog__close";
  dialogClose.setAttribute("aria-label", "Fechar diagrama ampliado");
  dialogClose.textContent = "×";
  dialogControls.append(zoomOut, zoomLabel, zoomIn, zoomReset, dialogClose);
  dialogHeader.append(dialogHeading, dialogControls);
  const dialogTrack = document.createElement("div");
  dialogTrack.className = "docs-diagram-dialog__track";
  dialogTrack.tabIndex = 0;
  dialogTrack.setAttribute("role", "region");
  dialogTrack.setAttribute("aria-label", "Área rolável do diagrama");
  const dialogSource = document.createElement("details");
  dialogSource.className = "docs-diagram-dialog__source";
  const dialogSourceSummary = document.createElement("summary");
  dialogSourceSummary.textContent = "Ver código do diagrama";
  dialogSource.append(dialogSourceSummary);
  dialogSurface.append(dialogHeader, dialogTrack, dialogSource);
  diagramDialog.append(dialogSurface);
  document.body.append(diagramDialog);

  let activeDiagram = null;
  let diagramOpener = null;
  let diagramScale = 1;
  const renderDiagramScale = () => {
    if (!activeDiagram) return;
    const viewBox = (activeDiagram.getAttribute("viewBox") || "").trim().split(/\s+/).map(Number);
    const width = Number(activeDiagram.getAttribute("width")) || viewBox[2];
    const height = Number(activeDiagram.getAttribute("height")) || viewBox[3];
    if (!width || !height) return;
    activeDiagram.style.width = Math.round(width * diagramScale) + "px";
    activeDiagram.style.height = Math.round(height * diagramScale) + "px";
    zoomLabel.textContent = Math.round(diagramScale * 100) + "%";
  };
  const setDiagramScale = (next) => {
    diagramScale = Math.max(0.5, Math.min(3, Math.round(next * 10) / 10));
    renderDiagramScale();
  };
  const resetDiagramView = () => {
    setDiagramScale(1);
    dialogTrack.scrollTo({ top: 0, left: 0, behavior: "auto" });
  };
  zoomOut.addEventListener("click", () => setDiagramScale(diagramScale - 0.2));
  zoomIn.addEventListener("click", () => setDiagramScale(diagramScale + 0.2));
  zoomReset.addEventListener("click", resetDiagramView);
  dialogClose.addEventListener("click", () => diagramDialog.close());
  diagramDialog.addEventListener("close", () => {
    activeDiagram = null;
    diagramOpener?.focus();
    diagramOpener = null;
  });
  diagramDialog.addEventListener("click", (event) => {
    if (event.target === diagramDialog) diagramDialog.close();
  });
  document.querySelectorAll("[data-docs-diagram-expand]").forEach((button) => {
    if (typeof diagramDialog.showModal !== "function") {
      button.hidden = true;
      return;
    }
    button.addEventListener("click", () => {
      const section = button.closest(".docs-diagram");
      const sourceSvg = section?.querySelector(".docs-diagram-svg");
      if (!sourceSvg) return;
      diagramOpener = button;
      activeDiagram = sourceSvg.cloneNode(true);
      activeDiagram.removeAttribute("class");
      dialogTrack.replaceChildren(activeDiagram);
      const sourcePre = section.querySelector(".docs-diagram-source pre");
      const code = sourcePre?.cloneNode(true);
      dialogSource.querySelector("pre")?.remove();
      if (code) dialogSource.append(code);
      setDiagramScale(1);
      dialogTrack.scrollTo({ top: 0, left: 0, behavior: "auto" });
      dialogSource.open = false;
      diagramDialog.showModal();
      dialogClose.focus();
    });
  });

  document.querySelectorAll("[data-docs-category]").forEach((group, index) => {
    const key = `arion-docs-category-${index}`;
    try {
      const saved = localStorage.getItem(key);
      if (saved !== null) group.open = saved === "open";
    } catch (_) { /* categories remain open by default */ }
    group.addEventListener("toggle", () => {
      try { localStorage.setItem(key, group.open ? "open" : "closed"); } catch (_) { /* local preference is optional */ }
    });
  });

  const toc = document.querySelector("[data-docs-toc]");
  const wideLayout = window.matchMedia("(min-width: 1280px)");
  if (toc) {
    const setTocLayout = () => { toc.open = wideLayout.matches; };
    wideLayout.addEventListener?.("change", setTocLayout);
    setTocLayout();

    const tocLinks = [...toc.querySelectorAll("[data-toc-link]")];
    const headings = tocLinks
      .map((link) => document.getElementById(link.dataset.tocLink))
      .filter(Boolean);
    if ("IntersectionObserver" in window && headings.length) {
      const visible = new Map();
      const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) visible.set(entry.target.id, entry.boundingClientRect.top);
          else visible.delete(entry.target.id);
        });
        const current = [...visible.entries()].sort((a, b) => Math.abs(a[1] - 105) - Math.abs(b[1] - 105))[0]?.[0];
        if (current) {
          tocLinks.forEach((link) => {
            const active = link.dataset.tocLink === current;
            link.classList.toggle("is-active", active);
            if (active) link.setAttribute("aria-current", "location");
            else link.removeAttribute("aria-current");
          });
        }
      }, { rootMargin: "-90px 0px -72% 0px", threshold: [0, 1] });
      headings.forEach((heading) => observer.observe(heading));
    }
  }

  const dictionary = document.querySelector(".docs-dictionary-index table");
  const dictionaryForm = document.querySelector("[data-doc-dictionary-form]");
  const dictionarySearch = document.querySelector("[data-doc-dictionary-search]");
  const dictionarySource = document.querySelector("[data-doc-dictionary-source]");
  const dictionaryCount = document.querySelector("[data-doc-dictionary-count]");
  if (dictionary && dictionaryForm && dictionarySearch && dictionarySource && dictionaryCount) {
    const rows = [...dictionary.querySelectorAll("tbody tr[data-doc-dictionary-row]")];
    const headers = [...dictionary.querySelectorAll("thead th")].map((cell) => cell.textContent.trim().toLocaleLowerCase());
    const sourceIndex = headers.indexOf("origem");
    const normalize = (value) => value.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase();
    const applyDictionaryFilters = () => {
      const query = normalize(dictionarySearch.value.trim());
      const source = normalize(dictionarySource.value);
      let visible = 0;
      rows.forEach((row) => {
        const sourceCell = sourceIndex >= 0 ? row.cells[sourceIndex]?.textContent || "" : "";
        const matches = normalize(row.textContent).includes(query)
          && (!source || normalize(sourceCell).includes(source));
        row.hidden = !matches;
        if (matches) visible += 1;
      });
      dictionaryCount.textContent = `${visible} de ${rows.length} campos`;
    };
    dictionarySearch.addEventListener("input", applyDictionaryFilters);
    dictionarySource.addEventListener("change", applyDictionaryFilters);
    applyDictionaryFilters();
  }

  document.querySelectorAll(".docs-markdown pre").forEach((pre) => {
    if (pre.closest(".docs-mermaid-source, .docs-diagram-source")) return;
    const code = pre.querySelector("code");
    if (!code) return;
    const languageClass = [...code.classList].find((name) => name.startsWith("language-"));
    const language = languageClass ? languageClass.slice("language-".length) : "código";
    const wrapper = document.createElement("div");
    wrapper.className = "docs-code-block";
    const toolbar = document.createElement("div");
    toolbar.className = "docs-code-toolbar";
    const label = document.createElement("span");
    label.className = "docs-code-language";
    label.textContent = language;
    const copy = document.createElement("button");
    copy.type = "button";
    copy.className = "docs-copy-code";
    copy.setAttribute("aria-label", "Copiar bloco de código");
    copy.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/></svg><span>Copiar</span>';
    copy.addEventListener("click", async () => {
      const status = copy.querySelector("span");
      try {
        await navigator.clipboard.writeText(code.textContent || "");
        status.textContent = "Copiado";
        window.setTimeout(() => { status.textContent = "Copiar"; }, 1400);
      } catch (_) {
        status.textContent = "Não foi possível copiar";
        window.setTimeout(() => { status.textContent = "Copiar"; }, 1800);
      }
    });
    toolbar.append(label, copy);
    wrapper.append(toolbar);
    pre.before(wrapper);
    wrapper.append(pre);
  });
})();


  document.querySelector("[data-release-picker]")?.addEventListener("change", (event) => {
    const url = new URL(window.location.href);
    url.searchParams.set("version", event.currentTarget.value);
    window.location.assign(url);
  });
