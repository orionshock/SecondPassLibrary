import { fetchJSONWithOptions, getCsrfToken, extractApiErrorMessage } from "../api.js";
import { $, escapeHtml, loadMeAndInitShell, setGlobalError } from "../layout.js";

function renderPreview(preview) {
  if (!preview || !preview.valid) return "<div class=\"muted\">No preview yet.</div>";
  const summary = preview.summary || {};
  const plan = preview.apply_plan || {};
  const warnings = Array.isArray(preview.warnings) ? preview.warnings : [];
  const rows = Array.isArray(preview.books) ? preview.books : [];
  const bookRows = rows
    .map((book) => {
      const match = book.match || {};
      const authors = Array.isArray(book.authors) ? book.authors.join(", ") : "";
      const importStatus = book.will_import ? "Will import" : "Will skip";
      return `
        <article class="book">
          <h3 class="book__title">${escapeHtml(book.title || "Book")}</h3>
          <div class="book__meta">
            ${authors ? `<div>${escapeHtml(authors)}</div>` : ""}
            <div>${escapeHtml(book.session_count)} session(s), ${escapeHtml(book.annotation_count)} annotation(s)</div>
            <div>${escapeHtml(book.bookmark_count)} bookmark(s), ${escapeHtml(book.highlight_count)} highlight(s), ${escapeHtml(book.commented_highlight_count)} commented highlight(s)</div>
            <div>Match: <span class="pill">${escapeHtml(match.status || "unmatched")}</span> ${escapeHtml(match.book_title || "")}</div>
            ${match.method ? `<div class="muted">Method: ${escapeHtml(match.method)} (${escapeHtml(match.confidence || "")})</div>` : ""}
            <div>${escapeHtml(importStatus)}</div>
            ${book.skip_reason ? `<div class="muted">Skip reason: ${escapeHtml(book.skip_reason)}</div>` : ""}
            ${book.warning ? `<div class="muted">${escapeHtml(book.warning)}</div>` : ""}
          </div>
        </article>
      `.trim();
    })
    .join("");
  const warningList = warnings.length
    ? `<ul>${warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join("")}</ul>`
    : "";
  const applyMessage = preview.can_apply
    ? "Matched data is ready for import."
    : "No matched local books. Nothing can be imported.";

  return `
    <div class="book__meta">
      <div>Scope: ${escapeHtml(preview.scope && preview.scope.type ? preview.scope.type : "")}</div>
      <div>${escapeHtml(summary.books)} book(s), ${escapeHtml(summary.sessions)} session(s), ${escapeHtml(summary.annotations)} annotation(s)</div>
      <div>${escapeHtml(applyMessage)}</div>
      <div class="muted">Preview only. Nothing will be imported yet.</div>
      <div class="muted">
        Plan: ${escapeHtml(plan.matched_books || 0)} matched book(s), ${escapeHtml(plan.skipped_books || 0)} skipped book(s),
        ${escapeHtml(plan.sessions_to_create || 0)} session(s), ${escapeHtml(plan.annotations_to_create || 0)} annotation(s).
      </div>
      ${warningList}
    </div>
    <div class="books">${bookRows || '<div class="muted">No books in export.</div>'}</div>
  `;
}

function renderApplyControls(preview) {
  if (!preview || !preview.valid) {
    return "Preview a file to see whether it can be imported.";
  }
  if (!preview.can_apply) {
    return "No matched local books can be imported.";
  }
  return `
    <div class="book__meta">
      <div>This will create new historical sessions for matched books. Existing sessions are not modified.</div>
      <button class="button" id="reading-import-apply-submit" type="button">Apply import</button>
    </div>
  `;
}

function renderApplyResult(result) {
  const summary = result && result.summary ? result.summary : {};
  const warnings = Array.isArray(result && result.warnings) ? result.warnings : [];
  const warningList = warnings.length
    ? `<ul>${warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join("")}</ul>`
    : "";
  return `
    <div class="book__meta">
      <div>Import completed.</div>
      <div>${escapeHtml(summary.books_matched || 0)} book(s) matched, ${escapeHtml(summary.books_skipped || 0)} book(s) skipped.</div>
      <div>${escapeHtml(summary.sessions_created || 0)} session(s), ${escapeHtml(summary.annotations_created || 0)} annotation(s) created.</div>
      <div>${escapeHtml(summary.bookmarks_created || 0)} bookmark(s), ${escapeHtml(summary.highlights_created || 0)} highlight(s), ${escapeHtml(summary.commented_highlights_created || 0)} commented highlight(s) created.</div>
      ${warningList}
    </div>
  `;
}

function renderErrors(error) {
  const body = error && error.body && typeof error.body === "object" ? error.body : {};
  const errors = Array.isArray(body.errors) ? body.errors : [];
  if (!errors.length) return escapeHtml(extractApiErrorMessage(error));
  return `<ul>${errors.map((err) => `<li><code>${escapeHtml(err.path || "$")}</code>: ${escapeHtml(err.message || "")}</li>`).join("")}</ul>`;
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
  if (!form || !input || !statusEl || !resultsEl || !applyControlsEl || !applyResultsEl || !submitBtn) return;

  function selectedFile() {
    return input.files && input.files.length ? input.files[0] : null;
  }

  function fileFormData() {
    const file = selectedFile();
    if (!file) return null;
    const formData = new FormData();
    formData.append("file", file);
    return formData;
  }

  input.addEventListener("change", () => {
    applyControlsEl.textContent = "Preview a file to see whether it can be imported.";
    applyResultsEl.innerHTML = "";
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
    applyControlsEl.textContent = "Preview a file to see whether it can be imported.";
    applyResultsEl.innerHTML = "";
    submitBtn.disabled = true;
    setGlobalError("");

    try {
      const csrf = getCsrfToken();
      const preview = await fetchJSONWithOptions("/api/v1/reading/import/preview/", {
        method: "POST",
        headers: {
          Accept: "application/json",
          ...(csrf ? { "X-CSRFToken": csrf } : {}),
        },
        body: formData,
      });
      statusEl.textContent = "Preview ready.";
      resultsEl.classList.remove("error");
      resultsEl.classList.remove("muted");
      resultsEl.innerHTML = renderPreview(preview);
      applyControlsEl.classList.remove("error");
      applyControlsEl.classList.remove("muted");
      applyControlsEl.innerHTML = renderApplyControls(preview);
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

  applyControlsEl.addEventListener("click", async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement) || target.id !== "reading-import-apply-submit") return;
    const formData = fileFormData();
    if (!formData) {
      applyResultsEl.classList.add("error");
      applyResultsEl.classList.remove("muted");
      applyResultsEl.textContent = "Choose the JSON export file again before applying.";
      return;
    }

    target.disabled = true;
    applyResultsEl.classList.remove("error");
    applyResultsEl.classList.remove("muted");
    applyResultsEl.textContent = "Applying import...";
    setGlobalError("");

    try {
      const csrf = getCsrfToken();
      const result = await fetchJSONWithOptions("/api/v1/reading/import/apply/", {
        method: "POST",
        headers: {
          Accept: "application/json",
          ...(csrf ? { "X-CSRFToken": csrf } : {}),
        },
        body: formData,
      });
      applyResultsEl.innerHTML = renderApplyResult(result);
    } catch (error) {
      applyResultsEl.classList.add("error");
      applyResultsEl.classList.remove("muted");
      applyResultsEl.innerHTML = renderErrors(error);
      setGlobalError(extractApiErrorMessage(error));
      target.disabled = false;
    }
  });
}
