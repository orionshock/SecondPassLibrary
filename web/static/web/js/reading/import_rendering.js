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
  const unmatchedPanel = renderUnmatchedPanel(preview);
  return `
    <div class="book__meta">
      <div>Scope: ${escapeHtml(preview.scope && preview.scope.type ? preview.scope.type : "")}</div>
      <div>${escapeHtml(summary.books)} book(s), ${escapeHtml(summary.sessions)} session(s), ${escapeHtml(summary.annotations)} annotation(s)</div>
      <div>${escapeHtml(applyMessage)}</div>
      <div class="muted">Annotation-level selection is not supported.</div>
      ${preview.can_apply ? '<div class="import-actions"><button class="button" id="reading-import-select-all-top" type="button">Select all</button><button class="button" id="reading-import-select-none-top" type="button">Select none</button></div>' : ""}
      ${warningList}
    </div>
    ${unmatchedPanel}
    <div class="books">${bookRows || '<div class="muted">No books in export.</div>'}</div>
  `;
}

function renderUnmatchedPanel(preview) {
  const books = Number(preview.unmatched_books || 0);
  const sessions = Number(preview.unmatched_sessions || 0);
  const count = Number(preview.unmatched_entries || 0);
  const url = preview.unmatched_download_url || "";
  if (!count || !url) return "";
  const countText = books && sessions
    ? `${books} ${books === 1 ? "book" : "books"} and ${sessions} ${sessions === 1 ? "session" : "sessions"} are not safe for server-side import.`
    : `${count} ${count === 1 ? "book or session is" : "books or sessions are"} not safe for server-side import. Download them for Reader-assisted import.`;
  return `
    <section class="card import-unmatched-panel">
      <h3 class="card__title">Some marks need the Reader.</h3>
      <p>${escapeHtml(countText)}</p>
      <p class="muted">Server import requires an exact book file-hash match and valid EPUB CFI-shaped locators. Use the Reader when the original book file is missing, different, or needs reanchoring.</p>
      <a class="button" href="${escapeHtml(url)}">Download unmatched marginalia</a>
    </section>
  `;
}

function renderBook(book, bookIndex) {
  const match = book.match || {};
  const authors = Array.isArray(book.authors) ? book.authors.join(", ") : "";
  const sessions = Array.isArray(book.sessions) ? book.sessions : [];
  const metadata = renderMetaList(bookMetadataParts(book, authors));
  const matchHtml = matchLine(match);
  const warningState = bookWarningState(book, sessions);
  const sessionRows = sessions
    .map((session) => renderSession(session, book, bookIndex, warningState.suppressedSessionWarning))
    .join("");
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
          <div class="book__meta import-book__meta">
            ${metadata ? `<div>${metadata}</div>` : ""}
            ${matchHtml ? `<div>${matchHtml}</div>` : ""}
            ${warningState.warnings.map((warning) => `<div class="muted import-warning">${escapeHtml(warning)}</div>`).join("")}
          </div>
        </div>
      </div>
      <div class="books">${sessionRows || '<div class="muted">No sessions in export.</div>'}</div>
    </article>
  `;
}

function bookMetadataParts(book, authors) {
  return [
    authors,
    book.series || "",
    countText(book.session_count, "session"),
    countText(book.annotation_count, "annotation"),
  ].filter(Boolean);
}

function matchLine(match) {
  const status = (match.status || "").trim();
  const title = (match.book_title || "").trim();
  const method = match.method ? match.methodLabel || humanizeMatchMethod(match.method) : "";
  const methodText = [method, match.confidence].filter(Boolean).join(" ");
  if (title) {
    return renderMetaList([`Matched to ${title}`, methodText]);
  }
  if (status && status !== "matched") {
    return renderMetaList([`Match ${status}`, methodText]);
  }
  return methodText ? renderMetaList(["Matched", methodText]) : "";
}

function humanizeMatchMethod(value) {
  return String(value || "").replace(/_/g, " ");
}

function bookWarningState(book, sessions) {
  const warnings = [];
  if (book.warning) warnings.push(book.warning);

  const sessionWarnings = sessions
    .map((session) => sessionWarning(session))
    .filter(Boolean);
  const uniqueSessionWarnings = [...new Set(sessionWarnings)];
  let suppressedSessionWarning = "";
  if (uniqueSessionWarnings.length === 1 && sessionWarnings.length === sessions.length && sessions.length > 1) {
    suppressedSessionWarning = uniqueSessionWarnings[0];
    warnings.push(pluralizeWarning(suppressedSessionWarning));
  }
  return { warnings: [...new Set(warnings)], suppressedSessionWarning };
}

function pluralizeWarning(warning) {
  if (warning === "Possible duplicate session.") return "Possible duplicate sessions found.";
  return warning;
}

function sessionWarning(session) {
  if (session.active_will_import_as_historical) return "Active export will import as historical.";
  return session.warning || "";
}

function countText(value, noun) {
  const count = Number(value || 0);
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

function renderMetaList(parts) {
  const items = parts
    .filter(Boolean)
    .map((part) => `<span class="meta-item">${escapeHtml(part)}</span>`)
    .join("");
  return items ? `<span class="meta-list">${items}</span>` : "";
}

function renderSession(session, book, bookIndex, suppressedWarning = "") {
  const selectable = Boolean(book.will_import && session.will_import);
  const checked = selectable ? "checked" : "";
  const disabled = selectable ? "" : "disabled";
  const warning = sessionWarning(session);
  const visibleWarning = warning === suppressedWarning ? "" : warning;
  const counts = [
    countText(session.annotation_count, "annotation"),
    countText(session.bookmark_count, "bookmark"),
    countText(session.highlight_count, "highlight"),
    countText(session.commented_highlight_count, "commented highlight"),
  ];
  const dateText = session.started_at ? formatDate(session.started_at) : "";
  const metadata = renderMetaList([session.status || "", dateText, ...counts]);
  const skippedText = session.needs_reader ? "Needs Reader" : "Skipped.";
  return `
    <article class="import-session" data-book-index="${bookIndex}" data-session-id="${escapeHtml(session.export_session_id || "")}">
      <div class="import-session__main">
        <label class="import-session__label">
        <input class="import-session-select" type="checkbox" data-book-index="${bookIndex}" data-session-id="${escapeHtml(session.export_session_id || "")}" ${checked} ${disabled} />
        ${escapeHtml(session.name || "Unnamed session")}
        </label>
        <div class="book__meta">
          <div>${metadata}</div>
          ${visibleWarning ? `<div class="muted import-warning import-warning--session">${escapeHtml(visibleWarning)}</div>` : ""}
        </div>
      </div>
      ${selectable ? `
        <input class="import-session-name" type="hidden" value="${escapeHtml(session.name || "")}" />
        <input class="import-session-notes" type="hidden" value="${escapeHtml(session.notes || "")}" />
        <button class="button import-session-edit" type="button">Edit name / note</button>
      ` : `<div class="muted">${escapeHtml(skippedText)}</div>`}
    </article>
  `;
}

function formatDate(value) {
  const raw = String(value || "");
  if (/^\d{4}-\d{2}-\d{2}/.test(raw)) return raw.slice(0, 10);
  return raw;
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
