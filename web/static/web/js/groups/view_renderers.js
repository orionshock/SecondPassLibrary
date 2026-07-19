import { escapeHtml } from "../layout.js";
import { shelfMetadataLine } from "../shelves/shared.js";
import { renderCoverPreviewStrip } from "../ui/cover_previews.js";
import { renderUserIdentity } from "../ui/identity.js";

function publishedYear(value) {
  const raw = value == null ? "" : String(value).trim();
  if (!raw) return "";
  const match = raw.match(/\d{4}/);
  return match ? match[0] : raw;
}

export function renderGroupViewBooks(payload) {
  const results = Array.isArray(payload && payload.results) ? payload.results : [];
  return results.map((book) => {
    const title = book && book.title ? String(book.title) : "(Untitled)";
    const subtitle = book && book.subtitle ? String(book.subtitle).trim() : "";
    const href = book && book.id
      ? `/library/books/${encodeURIComponent(String(book.id))}/`
      : "";
    const authors = Array.isArray(book && book.authors)
      ? book.authors.map((author) => author && author.name).filter(Boolean)
      : [];
    const seriesName = book && book.series && book.series.name
      ? String(book.series.name)
      : "";
    const seriesIndex = book && book.series_index != null && book.series_index !== ""
      ? String(book.series_index)
      : "";
    const series = seriesName ? `${seriesName}${seriesIndex ? ` ${seriesIndex}` : ""}` : "";
    const publisher = book && book.publisher ? String(book.publisher).trim() : "";
    const year = publishedYear(book && book.published_date);
    const publisherLine = [publisher, year].filter(Boolean).join(" - ");
    const coverUrl = book && book.cover_url ? String(book.cover_url) : "";
    const metadata = [authors.join(", "), series, publisherLine]
      .filter(Boolean)
      .map((value) => `<span>${escapeHtml(value)}</span>`)
      .join("");

    return `
      <article class="library-row group-view-book-row">
        <div class="book__cover" data-cover-url="${escapeHtml(coverUrl)}" data-cover-title="${escapeHtml(title)}"></div>
        <div class="library-row__body">
          <h3 class="library-row__title">${href ? `<a href="${escapeHtml(href)}">${escapeHtml(title)}</a>` : escapeHtml(title)}</h3>
          ${subtitle ? `<div class="library-row__subtitle">${escapeHtml(subtitle)}</div>` : ""}
          <div class="library-row__meta">${metadata || '<span class="muted">No metadata.</span>'}</div>
        </div>
      </article>
    `.trim();
  }).join("");
}

export function renderGroupViewMembers(payload) {
  const results = Array.isArray(payload && payload.results) ? payload.results : [];
  return results.map((membership) => {
    const user = membership && membership.user ? membership.user : membership;
    const identity = renderUserIdentity(user, { includeDisplayName: false }).outerHTML;
    const curator = membership && membership.is_curator
      ? '<span class="pill">Curator</span>'
      : "";
    return `<article class="group-view-member-row">${identity}${curator}</article>`;
  }).join("");
}

export function renderGroupViewShelves(payload) {
  const results = Array.isArray(payload && payload.results) ? payload.results : [];
  return results.map((shelf) => {
    const id = shelf && shelf.id != null ? String(shelf.id) : "";
    const name = shelf && shelf.name ? String(shelf.name) : "(Unnamed shelf)";
    const description = shelf && shelf.description ? String(shelf.description) : "";
    const href = id ? `/shelves/${encodeURIComponent(id)}/` : "";
    const metadata = shelfMetadataLine(shelf);
    const previews = renderCoverPreviewStrip(shelf && shelf.preview_books, {
      href,
      actionLabel: `View shelf ${name}`,
    });
    return `
      <article class="book shelf-list-card group-view-shelf-card">
        <div class="shelf-list-card__main">
          <h3 class="book__title shelf-list-card__title">${href ? `<a href="${escapeHtml(href)}">${escapeHtml(name)}</a>` : escapeHtml(name)}</h3>
          ${description ? `<div class="muted shelf-list-card__description">${escapeHtml(description)}</div>` : ""}
          ${metadata ? `<div class="muted shelf-list-card__metadata">${metadata}</div>` : ""}
        </div>
        ${previews}
      </article>
    `.trim();
  }).join("");
}
