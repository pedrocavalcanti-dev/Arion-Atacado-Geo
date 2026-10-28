(() => {
  "use strict";

  const layout = document.querySelector(".reports-layout");
  const toggle = document.querySelector("[data-sidebar-toggle]");
  if (!layout || !toggle) return;

  const key = "arion-relatorios:sidebar-collapsed";
  let collapsed = false;
  try { collapsed = window.localStorage.getItem(key) === "1"; } catch (_) { /* storage may be disabled */ }

  const apply = () => {
    layout.classList.toggle("is-sidebar-collapsed", collapsed);
    toggle.setAttribute("aria-expanded", String(!collapsed));
    toggle.setAttribute("aria-label", collapsed ? "Expandir navegação de relatórios" : "Recolher navegação de relatórios");
    toggle.title = collapsed ? "Expandir navegação" : "Recolher navegação";
    toggle.textContent = collapsed ? "›" : "‹";
  };

  apply();
  toggle.addEventListener("click", () => {
    collapsed = !collapsed;
    apply();
    try { window.localStorage.setItem(key, collapsed ? "1" : "0"); } catch (_) { /* storage may be disabled */ }
  });
})();
