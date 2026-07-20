import { fetchJSONWithOptions, getCsrfToken, extractApiErrorMessage } from "../api.js";
import { canAccessImports } from "../auth.js";
import { $, escapeHtml, loadMeAndInitShell, setGlobalError, visible } from "../layout.js";
import { setStatus } from "../ui/status.js";

function itemRefs(item) {
  return {
    bookId: item.book_id || "",
  };
}

function renderImportItem(item) {
  const status = item.status || "";
  const source = item.source_label || "Item unavailable";
  const message = item.safe_message || "";
  const refs = itemRefs(item);
  const sourceHtml = refs.bookId
    ? `<a href="/library/books/${encodeURIComponent(String(refs.bookId))}/">${escapeHtml(source)}</a>`
    : escapeHtml(source);

  return `<li class="import-result__item">
    <span class="pill">${escapeHtml(status)}</span>
    <span class="import-result__item-source">${sourceHtml}</span>
    ${message ? `<span class="muted import-result__item-message">- ${escapeHtml(message)}</span>` : ""}
  </li>`;
}

function resultCounts(result) {
  const counts = result.counts || {};
  return [
    ["imported", counts.imported],
    ["duplicate", counts.duplicate],
    ["conflict", counts.conflict],
    ["failed", counts.failed],
    ["skipped", counts.skipped],
  ].filter(([_key, value]) => value !== null && value !== undefined && value !== "");
}

function renderImportResult(result) {
  if (!result) return "";
  const source = result.source_label || "Source unavailable";
  const sourceType = result.source_type || "";
  const counts = resultCounts(result)
    .map(([key, value]) => `<span class="pill">${escapeHtml(key)}: ${escapeHtml(value)}</span>`)
    .join(" ");
  const items = Array.isArray(result.items) ? result.items : [];
  const itemRows = items.slice(0, 50).map(renderImportItem).join("");
  const extra = items.length > 50 ? `<div class="muted">Showing first 50 items.</div>` : "";

  return `<section class="book import-result" aria-label="Latest import result">
    <div class="import-result__summary">
      <span class="import-result__source">${escapeHtml(source)}</span>
      ${sourceType ? `<span class="pill">source type: ${escapeHtml(sourceType)}</span>` : ""}
      ${counts ? `<span class="import-result__counts">${counts}</span>` : ""}
    </div>
    <div class="book__meta import-result__details">
      <div>Import complete.</div>
      <div>Source: ${escapeHtml(source)}</div>
      ${sourceType ? `<div>Source type: ${escapeHtml(sourceType)}</div>` : ""}
      ${itemRows ? `<div class="import-result__items"><h4 class="card__title">Items</h4>${extra}<ul>${itemRows}</ul></div>` : ""}
    </div>
  </section>`;
}

export async function initImports() {
  const me = await loadMeAndInitShell();

  const notAllowedEl = $("#imports-not-allowed");
  const uploadForm = $("#imports-upload");
  const uploadStatus = $("#imports-upload-status");
  const fileInput = $("#import-file");
  const submitBtn = $("#imports-submit");
  const statusEl = $("#imports-status");
  const resultsEl = $("#imports-results");

  if (
    !statusEl ||
    !resultsEl ||
    !notAllowedEl ||
    !uploadForm ||
    !uploadStatus ||
    !fileInput ||
    !submitBtn
  ) {
    return;
  }

  const allowed = canAccessImports(me);

  visible(notAllowedEl, !allowed);
  visible(uploadForm, allowed);
  setStatus(
    statusEl,
    allowed ? "No import has been run in this browser session." : "Not allowed.",
    !allowed
  );

  function setUploadStatus(text, isError) {
    uploadStatus.textContent = text || "";
    uploadStatus.classList.toggle("error", !!isError);
  }

  function setBusy(isBusy) {
    fileInput.disabled = isBusy;
    submitBtn.disabled = isBusy;
    submitBtn.textContent = isBusy ? "Importing..." : "Upload";
  }

  uploadForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!allowed) return;

    const file = fileInput.files && fileInput.files.length ? fileInput.files[0] : null;
    if (!file) {
      setUploadStatus("Choose a file to upload.", true);
      return;
    }

    setGlobalError("");
    resultsEl.innerHTML = "";
    setBusy(true);
    setUploadStatus("Importing... large ZIP files may take a while.", false);
    setStatus(statusEl, "Import in progress.", false);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;

      const result = await fetchJSONWithOptions("/api/v1/library/imports/", {
        method: "POST",
        headers,
        body: formData,
      });

      resultsEl.innerHTML = renderImportResult(result);
      setUploadStatus("Import complete.", false);
      setStatus(statusEl, "Latest import result.", false);
      fileInput.value = "";
    } catch (err) {
      const message = extractApiErrorMessage(err);
      console.error("Import failed", err);
      setUploadStatus(message, true);
      setStatus(statusEl, "Import failed.", true);
      setGlobalError(message);
    } finally {
      setBusy(false);
    }
  });
}
