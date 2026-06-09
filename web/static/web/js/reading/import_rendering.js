import { extractApiErrorMessage } from "../api.js";
import { escapeHtml } from "../layout.js";

export function renderPreview(preview) {
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
      ${preview.can_apply ? '<div class="import-actions"><button class="button" id="reading-import-select-all-top" type="button">Select all</button><button class="button" id="reading-import-select-none-top" type="button">Select none</button></div>' : ""}
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
    ? `<input class="import-book-select import-book-select--large" type="checkbox" data-book-index="${bookIndex}" checked aria-label="Select all sessions for ${escapeHtml(book.title || "book")}" />`
    : "";
  const cover = book.cover_url
    ? `<img class="sessions-cover__img" src="${escapeHtml(book.cover_url)}" alt="Cover for ${escapeHtml(book.title || "Book")}" loading="lazy" />`
    : "Cover";
  return `
    <article class="book import-book" data-book-index="${bookIndex}" data-will-import="${book.will_import ? "true" : "false"}">
      <div class="import-book__header">
        <div class="import-book__select">${checkbox}</div>
        <div class="sessions-cover" aria-hidden="true">${cover}</div>
        <div class="import-book__main">
          <h3 class="book__title">${escapeHtml(book.title || "Book")}</h3>
          <div class="book__meta">
            ${authors ? `<div>${escapeHtml(authors)}</div>` : ""}
            <div>${escapeHtml(book.session_count)} session(s), ${escapeHtml(book.annotation_count)} annotation(s)</div>
            <div>Match: <span class="pill">${escapeHtml(match.status || "unmatched")}</span> ${escapeHtml(match.book_title || "")}</div>
            ${match.method ? `<div class="muted">Method: ${escapeHtml(match.method)} (${escapeHtml(match.confidence || "")})</div>` : ""}
            ${book.warning ? `<div class="muted">${escapeHtml(book.warning)}</div>` : ""}
          </div>
        </div>
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
    <article class="import-session" data-book-index="${bookIndex}" data-session-id="${escapeHtml(session.export_session_id || "")}">
      <div class="import-session__main">
        <label class="import-session__label">
        <input class="import-session-select" type="checkbox" data-book-index="${bookIndex}" data-session-id="${escapeHtml(session.export_session_id || "")}" ${checked} ${disabled} />
        ${escapeHtml(session.name || "Unnamed session")}
        </label>
        <div class="book__meta">
          <div>${escapeHtml(session.status || "")} - ${escapeHtml(session.started_at || "")}</div>
          <div>${escapeHtml(session.annotation_count)} annotation(s), ${escapeHtml(session.bookmark_count)} bookmark(s), ${escapeHtml(session.highlight_count)} highlight(s), ${escapeHtml(session.commented_highlight_count)} commented highlight(s)</div>
          ${warning ? `<div class="muted">${escapeHtml(warning)}</div>` : ""}
        </div>
      </div>
      ${selectable ? `
        <input class="import-session-name" type="hidden" value="${escapeHtml(session.name || "")}" />
        <input class="import-session-notes" type="hidden" value="${escapeHtml(session.notes || "")}" />
        <button class="button import-session-edit" type="button">Edit name / note</button>
      ` : '<div class="muted">Skipped.</div>'}
    </article>
  `;
}

export function renderApplyControls(preview) {
  if (!preview || !preview.valid) return "Preview a file to see whether it can be imported.";
  if (!preview.can_apply) return "No matched local books can be imported.";
  return `
    <div class="book__meta">
      <div>This will create new historical sessions for matched books. Existing sessions are not modified.</div>
      <div class="import-actions">
        <button class="button" id="reading-import-select-all" type="button">Select all</button>
        <button class="button" id="reading-import-select-none" type="button">Select none</button>
        <button class="button" id="reading-import-apply-submit" type="button">Apply import</button>
      </div>
    </div>
  `;
}

export function renderApplyResult(result) {
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

export function renderErrors(error) {
  const body = error && error.body && typeof error.body === "object" ? error.body : {};
  const errors = Array.isArray(body.errors) ? body.errors : [];
  if (!errors.length) return escapeHtml(extractApiErrorMessage(error));
  return `<ul>${errors.map((err) => `<li><code>${escapeHtml(err.path || "$")}</code>: ${escapeHtml(err.message || "")}</li>`).join("")}</ul>`;
}
