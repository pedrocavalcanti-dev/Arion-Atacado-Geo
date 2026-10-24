(() => {
  const forms = document.querySelectorAll("[data-db-stage-form]");
  forms.forEach((form) => {
    form.addEventListener("submit", () => {
      const button = form.querySelector("button[type=submit]");
      if (!button || button.disabled) return;
      button.disabled = true;
      button.textContent = form.dataset.pendingLabel || "Processando...";
      form.setAttribute("aria-busy", "true");
    }, { once: true });
  });
})();
