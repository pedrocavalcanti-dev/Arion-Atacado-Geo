(() => {
  "use strict";

  const wizard = document.querySelector("[data-competence-wizard]");
  const monthNames = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];

  function setProgress(status, title, stage, value, actualUpload = false) {
    const heading = status?.querySelector("[data-progress-title]");
    const stageLabel = status?.querySelector("[data-progress-stage]");
    const bar = status?.querySelector("[data-progress-bar]");
    const track = status?.querySelector('[role="progressbar"]');
    if (heading) heading.textContent = title;
    if (stageLabel) stageLabel.textContent = actualUpload ? `${value}% do arquivo enviado` : stage;
    if (bar) bar.style.width = `${Math.max(0, Math.min(100, value))}%`;
    if (track) {
      track.setAttribute("aria-valuenow", String(Math.max(0, Math.min(100, value))));
      track.setAttribute("aria-label", actualUpload ? "Percentual real do arquivo enviado" : "Etapas estimadas do processamento; não indica percentual exato de leitura");
    }
  }

  function installProgressUpload(form, {statusSelector, buttonSelector, titleSelector} = {}) {
    if (!form || form.dataset.progressReady === "true") return;
    form.dataset.progressReady = "true";
    const status = form.querySelector(statusSelector || "[data-submit-status], [data-upload-status]");
    const button = form.querySelector(buttonSelector || "[data-submit-import], [data-upload-submit]");
    const title = button?.textContent.trim() || "Enviar e validar arquivo";
    const error = status?.querySelector("[data-progress-error]");
    const retry = status?.querySelector("[data-upload-retry]");
    let submitting = false;
    let stageTimer = null;

    const resetButtons = () => {
      submitting = false;
      form.removeAttribute("aria-busy");
      if (button) {
        button.disabled = false;
        button.removeAttribute("aria-disabled");
        button.textContent = title;
      }
      form.querySelectorAll("[data-step-next], [data-step-back]").forEach((control) => { control.disabled = false; });
    };

    const fail = (messages, result = null) => {
      if (stageTimer) window.clearInterval(stageTimer);
      const detail = (Array.isArray(messages) ? messages : [messages]).filter(Boolean).join(" ");
      if (error) {
        error.textContent = detail || "Ocorreu uma falha de comunicação. Nenhum dado foi importado.";
        error.hidden = false;
      }
      status?.classList.add("is-error");
      const heading = status?.querySelector("[data-progress-title]");
      if (heading) heading.textContent = "Não foi possível validar esta planilha.";
      const stage = status?.querySelector("[data-progress-stage]");
      if (stage) stage.textContent = "Confira a mensagem e tente novamente.";
      if (retry) retry.hidden = false;
      resetButtons();
      if (result?.duplicate_period) {
        const month = form.querySelector("[data-report-month]");
        const year = form.querySelector("[data-report-year]");
        const availability = form.querySelector("[data-period-availability]");
        const availabilityMessage = form.querySelector("[data-period-message]");
        const availabilityLink = form.querySelector("[data-period-link]");
        const period = result.duplicate_period || `${monthNames[Number(month?.value) - 1] || ""} ${year?.value || ""}`.trim();
        if (availability) { availability.hidden = false; availability.classList.add("is-conflict"); }
        if (availabilityMessage) availabilityMessage.textContent = result.duplicate_archived
          ? `A competência ${period} está arquivada e não pode ser recriada.`
          : `Já existe uma competência Claro Multas para ${period}.`;
        if (availabilityLink && result.duplicate_url) {
          availabilityLink.href = result.duplicate_url;
          availabilityLink.hidden = false;
        } else if (availabilityLink) {
          availabilityLink.removeAttribute("href");
          availabilityLink.hidden = true;
        }
        form.querySelectorAll("[data-step-next], [data-submit-import]").forEach((control) => { control.disabled = true; });
        if (retry) retry.hidden = true;
        if (error) error.hidden = true;
        const heading = status?.querySelector("[data-progress-title]");
        const stage = status?.querySelector("[data-progress-stage]");
        if (heading) heading.textContent = "Competência já cadastrada.";
        if (stage) stage.textContent = "Abra o período existente para continuar.";
      }
    };

    const submit = () => {
      if (submitting) return;
      if (!form.reportValidity()) return;
      const payload = new FormData(form);
      const file = form.querySelector('input[type="file"]')?.files?.[0];
      const filename = form.querySelector("[data-progress-filename]");
      const workspaceFilename = form.querySelector("[data-workspace-file-name]");
      if (filename) filename.textContent = file?.name || "Competência sem arquivo original";
      if (workspaceFilename && file) workspaceFilename.textContent = `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MB`;
      if (error) { error.hidden = true; error.textContent = ""; }
      if (retry) retry.hidden = true;
      status?.classList.remove("is-error");
      if (status) status.hidden = false;
      submitting = true;
      form.setAttribute("aria-busy", "true");
      if (button) {
        button.disabled = true;
        button.setAttribute("aria-disabled", "true");
        button.textContent = file ? "Enviando e validando…" : "Criando competência…";
      }
      form.querySelectorAll("[data-step-next], [data-step-back]").forEach((control) => { control.disabled = true; });
      setProgress(status, file ? "Enviando arquivo" : "Criando competência", "Preparando envio", 0);

      const stages = [
        [35, "Validando Excel"],
        [50, "Identificando abas"],
        [65, "Detectando cabeçalhos"],
        [80, "Preparando prévia"],
        [95, "Finalizando"],
      ];
      let stageIndex = -1;
      const advanceStage = () => {
        stageIndex = Math.min(stageIndex + 1, stages.length - 1);
        const [value, label] = stages[stageIndex];
        setProgress(status, "Processando planilha", `${label} · etapa ${stageIndex + 1} de ${stages.length}`, value);
      };
      const startStages = () => {
        if (stageTimer || !submitting) return;
        advanceStage();
        stageTimer = window.setInterval(advanceStage, 1800);
      };

      const xhr = new XMLHttpRequest();
      xhr.open("POST", form.action, true);
      xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
      xhr.setRequestHeader("Accept", "application/json");
      xhr.upload.addEventListener("progress", (event) => {
        if (!event.lengthComputable || event.total <= 0) return;
        const percent = Math.round((event.loaded / event.total) * 100);
        setProgress(status, "Enviando arquivo", "Transferência real do arquivo", percent, true);
      });
      xhr.upload.addEventListener("loadend", startStages, {once: true});
      xhr.addEventListener("load", () => {
        if (stageTimer) window.clearInterval(stageTimer);
        let result;
        try { result = JSON.parse(xhr.responseText); } catch (_) { result = null; }
        if (xhr.status >= 200 && xhr.status < 300 && result?.ok && result.redirect_url) {
          setProgress(status, "Planilha validada", "Pronto", 100);
          window.location.assign(result.redirect_url);
          return;
        }
        fail(result?.messages || result?.error || "Não foi possível processar o arquivo. Nenhum dado foi importado.", result);
      });
      xhr.addEventListener("error", () => fail("Não foi possível processar o arquivo. Nenhum dado foi importado."));
      xhr.addEventListener("timeout", () => fail("A validação demorou mais que o esperado. Tente novamente."));
      xhr.timeout = 300000;
      xhr.send(payload);
      if (!file) startStages();
    };

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      submit();
    });
    retry?.addEventListener("click", submit);
  }

  if (wizard) {
    const panels = [...wizard.querySelectorAll("[data-step-panel]")];
    const indicators = [...wizard.querySelectorAll("[data-step-indicator]")];
    const fileInput = wizard.querySelector("[data-local-file]");
    const fileName = wizard.querySelector("[data-file-name]");
    const fileMeta = wizard.querySelector("[data-file-meta]");
    const fileError = wizard.querySelector("[data-file-error]");
    const dropzone = wizard.querySelector("[data-file-dropzone]");
    const month = wizard.querySelector("[data-report-month]");
    const year = wizard.querySelector("[data-report-year]");
    const availability = wizard.querySelector("[data-period-availability]");
    const serverConflict = wizard.querySelector("[data-period-conflict-server]");
    const availabilityMessage = wizard.querySelector("[data-period-message]");
    const availabilityLink = wizard.querySelector("[data-period-link]");
    const nextButton = wizard.querySelector("[data-step-next]");
    const submitButton = wizard.querySelector("[data-submit-import]");
    const maxBytes = 25 * 1024 * 1024;
    let selectedFile = null;
    let periodCheckController = null;
    let periodExists = wizard.dataset.periodExisting === "true";
    let periodCheckPending = false;

    const showConflict = (data) => {
      periodExists = Boolean(data?.exists);
      const alreadyArchived = Boolean(data?.archived);
      if (availability) availability.hidden = !periodExists;
      availability?.classList.toggle("is-conflict", periodExists);
      if (availabilityMessage) {
        availabilityMessage.textContent = alreadyArchived
          ? `${data.period} está arquivada e não pode ser recriada.`
          : `Já existe uma competência para ${data.period}.`;
      }
      if (availabilityLink) {
        if (data?.url) {
          availabilityLink.href = data.url;
          availabilityLink.hidden = false;
        } else {
          availabilityLink.removeAttribute("href");
          availabilityLink.hidden = true;
        }
      }
      if (nextButton) nextButton.disabled = periodExists || periodCheckPending;
      if (submitButton) submitButton.disabled = periodExists || periodCheckPending;
    };

    const checkPeriod = async () => {
      if (!month?.value || !year?.value) {
        if (availability) availability.hidden = true;
        periodExists = false;
        if (nextButton) nextButton.disabled = false;
        if (submitButton) submitButton.disabled = false;
        return;
      }
      periodCheckController?.abort();
      periodCheckController = new AbortController();
      periodCheckPending = true;
      if (nextButton) nextButton.disabled = true;
      if (submitButton) submitButton.disabled = true;
      if (availability) availability.hidden = false;
      if (availabilityMessage) availabilityMessage.textContent = "Verificando se o período já está cadastrado…";
      if (availabilityLink) availabilityLink.hidden = true;
      availability?.classList.remove("is-conflict");
      const params = new URLSearchParams({month: month.value, year: year.value});
      try {
        const response = await fetch(`${wizard.dataset.periodCheckUrl}?${params}`, {
          headers: {Accept: "application/json"}, signal: periodCheckController.signal,
        });
        const data = await response.json();
        periodCheckPending = false;
        if (response.ok) showConflict(data);
        else {
          if (availability) availability.hidden = true;
          periodExists = false;
          if (nextButton) nextButton.disabled = false;
          if (submitButton) submitButton.disabled = false;
        }
      } catch (error) {
        if (error.name === "AbortError") return;
        periodCheckPending = false;
        periodExists = false;
        if (availability) availability.hidden = true;
        if (nextButton) nextButton.disabled = false;
        if (submitButton) submitButton.disabled = false;
      }
    };

    if (periodExists) {
      if (serverConflict) serverConflict.hidden = true;
      showConflict({
        exists: true,
        period: wizard.dataset.existingPeriod,
        url: wizard.dataset.existingUrl,
        archived: wizard.dataset.existingArchived === "true",
      });
    }
    month?.addEventListener("change", checkPeriod);
    year?.addEventListener("change", checkPeriod);
    if (!periodExists) checkPeriod();

    const showStep = (step) => {
      panels.forEach((panel) => { panel.hidden = Number(panel.dataset.stepPanel) !== step; });
      indicators.forEach((indicator) => {
        const current = Number(indicator.dataset.stepIndicator) === step;
        indicator.classList.toggle("is-current", current);
        if (current) indicator.setAttribute("aria-current", "step");
        else indicator.removeAttribute("aria-current");
      });
      panels.find((panel) => Number(panel.dataset.stepPanel) === step)?.querySelector("h2")?.focus({preventScroll: true});
    };
    const setFileError = (message = "") => {
      fileError.textContent = message;
      fileError.hidden = !message;
      dropzone?.classList.toggle("has-error", Boolean(message));
    };
    const inspectFile = (file) => {
      selectedFile = null;
      setFileError();
      if (!file) {
        fileName.textContent = "Escolha ou arraste uma planilha";
        fileMeta.textContent = `Excel .xls ou .xlsx · até ${Math.round(maxBytes / 1024 / 1024)} MB`;
        return false;
      }
      const extension = file.name.split(".").pop()?.toLowerCase();
      if (!["xls", "xlsx"].includes(extension)) {
        setFileError("Formato não suportado. Selecione um arquivo .xls ou .xlsx.");
        fileName.textContent = file.name;
        fileMeta.textContent = "Formato inválido";
        return false;
      }
      if (file.size > maxBytes) {
        setFileError("O arquivo ultrapassa o limite de 25 MB.");
        fileName.textContent = file.name;
        fileMeta.textContent = `${(file.size / 1024 / 1024).toFixed(1)} MB · acima do limite`;
        return false;
      }
      selectedFile = file;
      fileName.textContent = file.name;
      fileMeta.textContent = `${(file.size / 1024 / 1024).toFixed(2)} MB · ${extension.toUpperCase()}`;
      return true;
    };

    fileInput?.addEventListener("change", () => inspectFile(fileInput.files?.[0]));
    dropzone?.addEventListener("dragover", (event) => { event.preventDefault(); dropzone.classList.add("is-dragging"); });
    dropzone?.addEventListener("dragleave", () => dropzone.classList.remove("is-dragging"));
    dropzone?.addEventListener("drop", (event) => {
      event.preventDefault();
      dropzone.classList.remove("is-dragging");
      const file = event.dataTransfer?.files?.[0];
      if (!file) return;
      try {
        const transfer = new DataTransfer();
        transfer.items.add(file);
        fileInput.files = transfer.files;
      } catch (_) { /* The selected-file summary still reflects the dropped file. */ }
      inspectFile(file);
    });

    wizard.addEventListener("click", (event) => {
      const next = event.target.closest("[data-step-next]");
      const back = event.target.closest("[data-step-back]");
      if (next) {
        if (!month?.value || !year?.value || periodCheckPending || periodExists || (fileInput?.files?.length && !inspectFile(fileInput.files[0]))) {
          if (!month?.value) month?.focus();
          else if (!year?.value) year?.focus();
          return;
        }
        const periodText = `${monthNames[Number(month.value) - 1] || ""} ${year.value}`.trim();
        wizard.querySelector("[data-review-period]").textContent = periodText;
        wizard.querySelector("[data-review-file]").textContent = selectedFile?.name ?? "Nenhum arquivo; competência será criada como rascunho";
        showStep(Number(next.dataset.stepNext));
      }
      if (back) showStep(Number(back.dataset.stepBack));
    });

    installProgressUpload(wizard, {statusSelector: "[data-submit-status]", buttonSelector: "[data-submit-import]"});
  }

  const workspaceUpload = document.querySelector("[data-workspace-upload]");
  if (workspaceUpload) {
    const file = workspaceUpload.querySelector("[data-local-file]");
    const name = workspaceUpload.querySelector("[data-workspace-file-name]");
    file?.addEventListener("change", () => {
      const selected = file.files?.[0];
      if (name) name.textContent = selected ? `${selected.name} · ${(selected.size / 1024 / 1024).toFixed(2)} MB` : "Nenhum arquivo selecionado · XLS ou XLSX · máximo 25 MB";
    });
    installProgressUpload(workspaceUpload, {statusSelector: "[data-upload-status]", buttonSelector: "[data-upload-submit]"});
  }

  const importForm = document.querySelector("[data-import-form]");
  if (importForm) {
    let submitting = false;
    importForm.addEventListener("submit", (event) => {
      if (submitting) { event.preventDefault(); return; }
      submitting = true;
      const status = importForm.querySelector("[data-import-status]");
      const copy = importForm.querySelector("[data-import-status-copy]");
      const submitter = event.submitter;
      if (status) status.hidden = false;
      if (copy) copy.textContent = submitter?.value === "preview" ? "Atualizando a prévia da planilha…" : "Validando e importando linhas…";
      importForm.querySelectorAll("button[type=submit]").forEach((button) => {
        if (button !== submitter) button.disabled = true;
      });
      if (submitter) {
        submitter.disabled = true;
        submitter.textContent = submitter.value === "preview" ? "Lendo planilha…" : "Importando…";
      }
    });
  }
})();
