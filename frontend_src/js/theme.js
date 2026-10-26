(() => {
  const root = document.documentElement;
  const serverTheme = root.dataset.userTheme;
  let theme = serverTheme === "light" || serverTheme === "dark" ? serverTheme : "dark";
  if (serverTheme !== "light" && serverTheme !== "dark") {
    try { theme = localStorage.getItem("arion-theme") === "light" ? "light" : "dark"; } catch (_) { /* storage can be disabled */ }
  } else {
    try { localStorage.setItem("arion-theme", theme); } catch (_) { /* server preference remains authoritative */ }
  }
  root.dataset.theme = theme;
})();
