(() => {
  const standaloneQuery = window.matchMedia?.("(display-mode: standalone)");
  const isStandalone = () => Boolean(standaloneQuery?.matches || window.navigator.standalone === true);
  const installButtons = [...document.querySelectorAll("[data-pwa-install]")];
  const installedLabels = [...document.querySelectorAll("[data-pwa-installed]")];
  const installHelp = document.querySelector("[data-pwa-install-help]");
  const updateNotice = document.querySelector("[data-pwa-update]");
  const launchScreen = document.querySelector("[data-pwa-launch]");
  let installPrompt = null;
  let waitingWorker = null;
  let shouldReloadForUpdate = false;

  function updateInstallControls() {
    const installed = isStandalone();
    const ios = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
    installButtons.forEach((button) => {
      button.hidden = installed || (!installPrompt && !ios);
      button.dataset.installHelp = ios && !installPrompt ? "ios" : "native";
    });
    installedLabels.forEach((label) => { label.hidden = !installed; });
  }

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    installPrompt = event;
    updateInstallControls();
  });

  window.addEventListener("appinstalled", () => {
    installPrompt = null;
    updateInstallControls();
  });

  installButtons.forEach((button) => button.addEventListener("click", async () => {
    document.querySelector("[data-mobile-navigation]")?.close();
    if (button.dataset.installHelp === "ios") {
      installHelp?.showModal();
      return;
    }
    if (!installPrompt) return;
    const prompt = installPrompt;
    installPrompt = null;
    updateInstallControls();
    await prompt.prompt();
    await prompt.userChoice;
  }));

  document.querySelector("[data-pwa-install-close]")?.addEventListener("click", () => installHelp?.close());
  installHelp?.addEventListener("click", (event) => { if (event.target === installHelp) installHelp.close(); });

  const launchClass = "pwa-launch-pending";
  if (document.documentElement.classList.contains(launchClass)) {
    requestAnimationFrame(() => document.documentElement.classList.remove(launchClass));
    window.setTimeout(() => {
      document.documentElement.classList.remove(launchClass);
      launchScreen?.remove();
    }, 720);
  } else {
    launchScreen?.remove();
  }

  const menu = document.querySelector("[data-mobile-navigation]");
  const openMenu = document.querySelector("[data-mobile-nav-open]");
  const closeMenu = document.querySelector("[data-mobile-nav-close]");
  if (menu && openMenu) {
    openMenu.addEventListener("click", () => {
      menu.showModal();
      openMenu.setAttribute("aria-expanded", "true");
      closeMenu?.focus();
    });
    const restoreMenuFocus = () => {
      openMenu.setAttribute("aria-expanded", "false");
      if (window.matchMedia("(max-width: 900px)").matches) openMenu.focus();
    };
    closeMenu?.addEventListener("click", () => menu.close());
    menu.addEventListener("close", restoreMenuFocus);
    menu.addEventListener("click", (event) => { if (event.target === menu) menu.close(); });
    menu.querySelectorAll("a").forEach((link) => link.addEventListener("click", () => menu.close()));
    window.matchMedia("(min-width: 901px)").addEventListener("change", (event) => { if (event.matches && menu.open) menu.close(); });
  }

  const dismissUpdate = () => { if (updateNotice) updateNotice.hidden = true; };
  document.querySelector("[data-pwa-update-dismiss]")?.addEventListener("click", dismissUpdate);
  document.querySelector("[data-pwa-update-accept]")?.addEventListener("click", () => {
    if (!waitingWorker) return;
    shouldReloadForUpdate = true;
    waitingWorker.postMessage({ type: "SKIP_WAITING" });
  });
  navigator.serviceWorker?.addEventListener("controllerchange", () => {
    if (shouldReloadForUpdate) window.location.reload();
  });

  async function registerWorker() {
    if (!("serviceWorker" in navigator) || !window.isSecureContext) return;
    try {
      const registration = await navigator.serviceWorker.register("/service-worker.js", { scope: "/", updateViaCache: "none" });
      const showUpdate = (worker) => {
        if (!navigator.serviceWorker.controller || !worker) return;
        waitingWorker = worker;
        if (updateNotice) updateNotice.hidden = false;
      };
      showUpdate(registration.waiting);
      registration.addEventListener("updatefound", () => {
        const installing = registration.installing;
        installing?.addEventListener("statechange", () => {
          if (installing.state === "installed") showUpdate(registration.waiting);
        });
      });
      await registration.update();
    } catch {
      // The application remains fully usable when offline support is unavailable.
    }
  }

  updateInstallControls();
  standaloneQuery?.addEventListener("change", updateInstallControls);
  registerWorker();
})();
