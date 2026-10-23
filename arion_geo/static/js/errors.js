(() => {
  const sameOriginReferrer = () => {
    if (!document.referrer) return "";
    try {
      const referrer = new URL(document.referrer);
      return referrer.origin === window.location.origin ? referrer.href : "";
    } catch (_) {
      return "";
    }
  };

  document.querySelector("[data-history-back]")?.addEventListener("click", event => {
    const referrer = sameOriginReferrer();
    if (!referrer || history.length < 2) return;
    event.preventDefault();
    history.back();
  });

  document.querySelector("[data-error-retry]")?.addEventListener("click", event => {
    const control = event.currentTarget;
    if (control.dataset.errorCode === "CSRF_FAILED") {
      const referrer = sameOriginReferrer();
      if (referrer) {
        event.preventDefault();
        window.location.assign(referrer);
      }
      return;
    }
    event.preventDefault();
    window.location.reload();
  });
})();
