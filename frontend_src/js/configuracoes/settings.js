(() => {
  const sections = document.querySelector(".settings-mobile-sections");
  if (sections) {
    sections.addEventListener("keydown", event => {
      if (event.key === "Escape" && sections.open) {
        sections.open = false;
        sections.querySelector("summary")?.focus();
      }
    });
    document.addEventListener("pointerdown", event => {
      if (sections.open && !sections.contains(event.target)) sections.open = false;
    });
  }

  const permissionModules = document.querySelectorAll("[data-permission-modules] .permission-module");
  if (permissionModules.length) {
    const mobileLayout = window.matchMedia("(max-width: 680px)");
    const syncPermissionModules = () => permissionModules.forEach(module => { module.open = !mobileLayout.matches; });
    syncPermissionModules();
    mobileLayout.addEventListener("change", syncPermissionModules);
  }

  const status = document.querySelector("[data-theme-save-status]");
  if (!status) return;

  window.addEventListener("arion:themechange", () => {
    status.textContent = "Tema aplicado. Salvando sua preferência…";
  });
  window.addEventListener("arion:theme-saved", () => {
    status.textContent = "Preferência de aparência salva.";
  });
  window.addEventListener("arion:theme-save-failed", () => {
    status.textContent = "Tema aplicado nesta tela, mas não foi possível salvar. Atualize e tente novamente.";
  });
})();
