document.addEventListener("click", (event) => {
  const opener = event.target.closest("[data-dialog-open]");
  if (opener) {
    const dialog = document.getElementById(opener.dataset.dialogOpen);
    if (dialog && typeof dialog.showModal === "function") dialog.showModal();
  }

  const closer = event.target.closest("[data-dialog-close]");
  if (closer) closer.closest("dialog")?.close();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    document.querySelectorAll("dialog[open]").forEach((dialog) => dialog.close());
  }
});
