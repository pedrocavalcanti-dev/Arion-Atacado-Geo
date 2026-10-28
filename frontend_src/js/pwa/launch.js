(() => {
  const standalone = window.matchMedia?.("(display-mode: standalone)").matches || window.navigator.standalone === true;
  const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  if (!standalone || reducedMotion) return;
  try {
    if (window.sessionStorage.getItem("arion-pwa-launch-shown") === "1") return;
    window.sessionStorage.setItem("arion-pwa-launch-shown", "1");
  } catch {
    // Storage may be unavailable in a restricted browser context.
  }
  document.documentElement.classList.add("pwa-launch-pending");
})();
