import { fetchJSONWithOptions, getCsrfToken, extractApiErrorMessage } from "../api.js";
import { $, loadMeAndInitShell, setGlobalError } from "../layout.js";
import { bindImportEditModal } from "./import_edit_modal.js";
import {
  renderApplyControls,
  renderApplyResult,
  renderErrors,
  renderPreview,
} from "./import_rendering.js";
import {
  bindSelectionControls,
  buildSelection,
  handleSelectAllNoneClick,
  syncApplyState,
} from "./import_selection.js";

function clearImportData({ input, resultsEl, applyControlsEl, statusEl }) {
  input.value = "";
  resultsEl.innerHTML = '<div class="muted">No preview yet.</div>';
  applyControlsEl.textContent = "Preview a file to see whether it can be imported.";
  if (statusEl) statusEl.textContent = "";
}

export async function initReadingImportPreview() {
  await loadMeAndInitShell();
  const form = $("#reading-import-preview-form");
  const input = $("#reading-import-file");
  const statusEl = $("#reading-import-preview-status");
  const resultsEl = $("#reading-import-preview-results");
  const applyControlsEl = $("#reading-import-apply-controls");
  const applyResultsEl = $("#reading-import-apply-results");
  const submitBtn = $("#reading-import-preview-submit");
  const modal = $("#reading-import-session-modal");
  const modalForm = $("#reading-import-session-modal-form");
  const modalName = $("#reading-import-session-modal-name");
  const modalNotes = $("#reading-import-session-modal-notes");
  const modalCancel = $("#reading-import-session-modal-cancel");
  if (!form || !input || !statusEl || !resultsEl || !applyControlsEl || !applyResultsEl || !submitBtn || !modal || !modalForm || !modalName || !modalNotes || !modalCancel) return;
  let currentPreview = null;
  let currentImportToken = "";

  function fileFormData() {
    const file = input.files && input.files.length ? input.files[0] : null;
    if (!file) return null;
    const formData = new FormData();
    formData.append("file", file);
    return formData;
  }

  input.addEventListener("change", () => {
    currentPreview = null;
    currentImportToken = "";
    resultsEl.innerHTML = '<div class="muted">No preview yet.</div>';
    applyControlsEl.textContent = "Preview a file to see whether it can be imported.";
    applyResultsEl.innerHTML = "";
    statusEl.textContent = "";
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = fileFormData();
    if (!formData) {
      statusEl.textContent = "Choose a JSON export file.";
      return;
    }
    statusEl.textContent = "Validating...";
    resultsEl.innerHTML = "";
    applyResultsEl.innerHTML = "";
    submitBtn.disabled = true;
    setGlobalError("");
    try {
      const csrf = getCsrfToken();
      currentPreview = await fetchJSONWithOptions("/api/v1/reading/import/preview/", {
        method: "POST",
        headers: { Accept: "application/json", ...(csrf ? { "X-CSRFToken": csrf } : {}) },
        body: formData,
      });
      currentImportToken = currentPreview.import_token || "";
      statusEl.textContent = "Preview ready.";
      resultsEl.classList.remove("error", "muted");
      resultsEl.innerHTML = renderPreview(currentPreview);
      applyControlsEl.classList.remove("error", "muted");
      applyControlsEl.innerHTML = renderApplyControls(currentPreview);
      syncApplyState(resultsEl, applyControlsEl);
    } catch (error) {
      statusEl.textContent = "Preview failed.";
      resultsEl.classList.add("error");
      resultsEl.classList.remove("muted");
      resultsEl.innerHTML = renderErrors(error);
      applyControlsEl.textContent = "Preview a file to see whether it can be imported.";
      setGlobalError(extractApiErrorMessage(error));
    } finally {
      submitBtn.disabled = false;
    }
  });

  bindSelectionControls({ resultsEl, applyControlsEl });
  bindImportEditModal({ resultsEl, modal, modalForm, modalName, modalNotes, modalCancel });

  applyControlsEl.addEventListener("click", async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (handleSelectAllNoneClick({ target, resultsEl, applyControlsEl })) {
      return;
    }
    if (target.id !== "reading-import-apply-submit") return;
    if (!currentImportToken || !currentPreview) {
      applyResultsEl.classList.add("error");
      applyResultsEl.textContent = "Choose and preview the JSON export file again before applying.";
      return;
    }
    const formData = new FormData();
    formData.append("import_token", currentImportToken);
    formData.append("selection", JSON.stringify(buildSelection(currentPreview, resultsEl)));
    target.disabled = true;
    applyResultsEl.classList.remove("error", "muted");
    applyResultsEl.textContent = "Applying import...";
    setGlobalError("");
    try {
      const csrf = getCsrfToken();
      const result = await fetchJSONWithOptions("/api/v1/reading/import/apply/", {
        method: "POST",
        headers: { Accept: "application/json", ...(csrf ? { "X-CSRFToken": csrf } : {}) },
        body: formData,
      });
      applyResultsEl.innerHTML = renderApplyResult(result);
      currentPreview = null;
      currentImportToken = "";
      clearImportData({ input, resultsEl, applyControlsEl, statusEl });
    } catch (error) {
      applyResultsEl.classList.add("error");
      applyResultsEl.innerHTML = renderErrors(error);
      setGlobalError(extractApiErrorMessage(error));
      target.disabled = false;
    }
  });
}
