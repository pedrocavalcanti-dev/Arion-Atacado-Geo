(() => {
  const root = document.documentElement;
  const userMenu = document.querySelector(".user-menu");
  const summary = userMenu?.querySelector("summary");
  const themeToggle = document.querySelector("[data-theme-toggle]");
  const themeColorMeta = document.querySelector('meta[name="theme-color"]');
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const MENU_CLOSE_MS = 140;
  let closeTimer = null;

  /* ---------- Tema ---------- */
  function currentTheme() {
    return root.dataset.theme === "light" ? "light" : "dark";
  }

  function syncThemeMenu() {
    const light = currentTheme() === "light";
    if (themeColorMeta) themeColorMeta.setAttribute("content", light ? "#f1f2ef" : "#090a0a");
    if (themeToggle) {
      themeToggle.setAttribute("aria-checked", String(light));
      themeToggle.setAttribute("aria-label", light ? "Ativar tema escuro" : "Ativar tema claro");
    }
    document.querySelectorAll("[data-theme-option]").forEach((option) => {
      option.classList.toggle("is-active", option.dataset.themeOption === currentTheme());
    });
  }

  function setTheme(theme) {
    const next = theme === "light" ? "light" : "dark";
    root.dataset.theme = next;
    try { localStorage.setItem("arion-theme", next); } catch (_) { /* preference remains for this page */ }
    syncThemeMenu();
    // Evento global: outros módulos (mapa, dashboard) reagem sem reload.
    window.dispatchEvent(new CustomEvent("arion:themechange", { detail: { theme: next } }));
  }

  syncThemeMenu();
  themeToggle?.addEventListener("click", () => setTheme(currentTheme() === "light" ? "dark" : "light"));
  document.querySelectorAll("[data-theme-option]").forEach((option) => {
    option.addEventListener("click", () => setTheme(option.dataset.themeOption));
  });

  /* ---------- Dropdown do usuário ---------- */
  function syncExpanded() {
    summary?.setAttribute("aria-expanded", String(Boolean(userMenu?.open)));
  }

  function closeMenu({ focusSummary = false } = {}) {
    if (!userMenu?.open || userMenu.classList.contains("is-closing")) return;
    const finish = () => {
      userMenu.classList.remove("is-closing");
      userMenu.open = false;
      syncExpanded();
      if (focusSummary) summary?.focus();
    };
    if (reducedMotion.matches) {
      finish();
      return;
    }
    userMenu.classList.add("is-closing");
    window.clearTimeout(closeTimer);
    closeTimer = window.setTimeout(finish, MENU_CLOSE_MS);
  }

  summary?.addEventListener("click", (event) => {
    if (userMenu.open) {
      event.preventDefault();
      closeMenu();
      return;
    }
    window.setTimeout(syncExpanded, 0);
  });

  document.addEventListener("click", (event) => {
    if (userMenu && !userMenu.contains(event.target)) closeMenu();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && userMenu?.open) closeMenu({ focusSummary: true });
  });

  /* ---------- Toasts ---------- */
  window.setTimeout(() => {
    document.querySelectorAll(".toast").forEach((toast) => {
      toast.classList.add("is-leaving");
      window.setTimeout(() => toast.remove(), 250);
    });
  }, 5000);
})();
