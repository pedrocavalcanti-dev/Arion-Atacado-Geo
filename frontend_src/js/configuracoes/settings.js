(() => {
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
