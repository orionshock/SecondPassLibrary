import { fetchJSONWithOptions, getCsrfToken, extractApiErrorMessage } from "../api.js";
import { $, escapeHtml, loadMeAndInitShell, setGlobalError } from "../layout.js";

function renderPreview(preview) {
  if (!preview || !preview.valid) return "<div class=\"muted\">No preview yet.</div>";
  const summary = preview.summary || {};
  const rows = Array.isArray(preview.books) ? preview.books : [];
  const bookRows = rows.map((book, bookIndex) => renderBook(book, bookIndex)).join("");
  const warnings = Array.isArray(preview.warnings) ? preview.warnings : [];
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
      <div class="muted">Annotation-level selection is not supported.</div>
      ${warningList}
    </div>
    <div class="books">${bookRows || '<div class="muted">No books in export.</div>'}</div>
  `;
}

function renderBook(book, bookIndex) {
  const match = book.match || {};
  const authors = Array.isArray(book.authors) ? book.authors.join(", ") : "";
  const sessions = Array.isArray(book.sessions) ? book.sessions : [];
  const sessionRows = sessions.map((session) => renderSession(session, book, bookIndex)).join("");
  const checkbox = book.will_import
    ? `<input class="import-book-select" type="checkbox" data-book-index="${bookIndex}" checked aria-label="Select all sessions for ${escapeHtml(book.title || "book")}" />`
    : "";
  return `
    <article class="book import-book" data-book-index="${bookIndex}" data-will-import="${book.will_import ? "true" : "false"}">
      <h3 class="book__title">${checkbox}${escapeHtml(book.title || "Book")}</h3>
      <div class="book__meta">
        ${authors ? `<div>${escapeHtml(authors)}</div>` : ""}
        <div>${escapeHtml(book.session_count)} session(s), ${escapeHtml(book.annotation_count)} annotation(s)</div>
        <div>Match: <span class="pill">${escapeHtml(match.status || "unmatched")}</span> ${escapeHtml(match.book_title || "")}</div>
        ${match.method ? `<div class="muted">Method: ${escapeHtml(match.method)} (${escapeHtml(match.confidence || "")})</div>` : ""}
        ${book.warning ? `<div class="muted">${escapeHtml(book.warning)}</div>` : ""}
      </div>
      <div class="books">${sessionRows || '<div class="muted">No sessions in export.</div>'}</div>
    </article>
  `;
}

function renderSession(session, book, bookIndex) {
  const selectable = Boolean(book.will_import && session.will_import);
  const checked = selectable ? "checked" : "";
  const disabled = selectable ? "" : "disabled";
  const warning = session.active_will_import_as_historical
    ? "Active export will import as historical."
    : session.warning || "";
  return `
    <article class="book import-session" data-book-index="${bookIndex}" data-session-id="${escapeHtml(session.export_session_id || "")}">
      <label>
        <input class="import-session-select" type="checkbox" data-book-index="${bookIndex}" data-session-id="${escapeHtml(session.export_session_id || "")}" ${checked} ${disabled} />
        ${escapeHtml(session.name || "Unnamed session")}
      </label>
      <div class="book__meta">
        <div>${escapeHtml(session.status || "")} - ${escapeHtml(session.started_at || "")}</div>
        <div>${escapeHtml(session.annotation_count)} annotation(s), ${escapeHtml(session.bookmark_count)} bookmark(s), ${escapeHtml(session.highlight_count)} highlight(s), ${escapeHtml(session.commented_highlight_count)} commented highlight(s)</div>
        ${warning ? `<div class="muted">${escapeHtml(warning)}</div>` : ""}
      </div>
      ${selectable ? `
        <label>Import name</label>
        <input class="form-control import-session-name" type="text" value="${escapeHtml(session.name || "")}" />
        <label>Import notes</label>
        <textarea class="form-control import-session-notes" rows="3">${escapeHtml(session.notes || "")}</textarea>
      ` : '<div class="muted">Skipped.</div>'}
    </article>
  `;
}

function renderApplyControls(preview) {
  if (!preview || !preview.valid) return "Preview a file to see whether it can be imported.";
  if (!preview.can_apply) return "No matched local books can be imported.";
  return `
    <div class="book__meta">
      <div>This will create new historical sessions for matched books. Existing sessions are not modified.</div>
      <div style="display:flex; gap: 10px; flex-wrap: wrap;">
        <button class="button" id="reading-import-select-all" type="button">Select all</button>
        <button class="button" id="reading-import-select-none" type="button">Select none</button>
        <button class="button" id="reading-import-apply-submit" type="button">Apply import</button>
      </div>
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

function syncApplyState(resultsEl, applyControlsEl) {
  resultsEl.querySelectorAll(".import-book-select").forEach((bookBox) => {
    const boxes = [...resultsEl.querySelectorAll(`.import-session-select[data-book-index="${bookBox.dataset.bookIndex}"]:not(:disabled)`)];
    const selected = boxes.filter((box) => box.checked).length;
    bookBox.checked = boxes.length > 0 && selected === boxes.length;
    bookBox.indeterminate = selected > 0 && selected < boxes.length;
  });
  const anySelected = Boolean(resultsEl.querySelector(".import-session-select:checked:not(:disabled)"));
  const applyBtn = applyControlsEl.querySelector("#reading-import-apply-submit");
  if (applyBtn) applyBtn.disabled = !anySelected;
}

function buildSelection(preview, resultsEl) {
  const books = [];
  (preview.books || []).forEach((book, bookIndex) => {
    const sessions = [];
    resultsEl.querySelectorAll(`.import-session-select[data-book-index="${bookIndex}"]:checked:not(:disabled)`).forEach((box) => {
      const row = box.closest(".import-session");
      sessions.push({
        export_session_id: box.dataset.sessionId || "",
        selected: true,
        name: row.querySelector(".import-session-name")?.value || "",
        notes: row.querySelector(".import-session-notes")?.value || "",
      });
    });
    if (sessions.length) {
      books.push({
        source: book.source || "",
        file_hash: book.file_hash || "",
        title: book.title || "",
        sessions,
      });
    }
  });
  return { books };
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
  let currentPreview = null;

  function fileFormData() {
    const file = input.files && input.files.length ? input.files[0] : null;
    if (!file) return null;
    const formData = new FormData();
    formData.append("file", file);
    return formData;
  }

  input.addEventListener("change", () => {
    currentPreview = null;
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

  resultsEl.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLInputElement)) return;
    if (target.classList.contains("import-book-select")) {
      resultsEl.querySelectorAll(`.import-session-select[data-book-index="${target.dataset.bookIndex}"]:not(:disabled)`).forEach((box) => {
        box.checked = target.checked;
      });
    }
    syncApplyState(resultsEl, applyControlsEl);
  });

  applyControlsEl.addEventListener("click", async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.id === "reading-import-select-all" || target.id === "reading-import-select-none") {
      const checked = target.id === "reading-import-select-all";
      resultsEl.querySelectorAll(".import-session-select:not(:disabled)").forEach((box) => {
        box.checked = checked;
      });
      syncApplyState(resultsEl, applyControlsEl);
      return;
    }
    if (target.id !== "reading-import-apply-submit") return;
    const formData = fileFormData();
    if (!formData || !currentPreview) {
      applyResultsEl.classList.add("error");
      applyResultsEl.textContent = "Choose and preview the JSON export file again before applying.";
      return;
    }
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
    } catch (error) {
      applyResultsEl.classList.add("error");
      applyResultsEl.innerHTML = renderErrors(error);
      setGlobalError(extractApiErrorMessage(error));
      target.disabled = false;
    }
  });
}
