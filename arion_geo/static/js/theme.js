(() => {
  let theme = "dark";
  try { theme = localStorage.getItem("arion-theme") === "light" ? "light" : "dark"; } catch (_) { /* storage can be disabled */ }
  document.documentElement.dataset.theme = theme;
})();
