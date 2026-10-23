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

  document.querySelectorAll(".docs-markdown pre").forEach((pre) => {
    if (pre.closest(".docs-mermaid-source")) return;
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
