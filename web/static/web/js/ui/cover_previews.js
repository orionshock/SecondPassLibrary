import { escapeHtml } from "../layout.js";

function previewBooks(books) {
  return Array.isArray(books) ? books.filter((book) => book && book.title) : [];
}

function bookDetailHref(book) {
  return book && book.id ? `/library/books/${encodeURIComponent(String(book.id))}/` : "";
}

export function renderCoverPreviewStrip(books, options = {}) {
  const visibleBooks = previewBooks(books);
  if (!visibleBooks.length) return "";

  const action = options.action ? String(options.action) : "";
  const contextId = options.contextId ? String(options.contextId) : "";
  const contextName = options.contextName ? String(options.contextName) : "";
  const actionLabel = options.actionLabel ? String(options.actionLabel) : "View books";
  const contextHref = options.href ? String(options.href) : "";

  const buttons = visibleBooks
    .map((book) => {
      const title = String(book.title || "Untitled");
      const coverUrl = book.cover_url ? String(book.cover_url) : "";
      const href = contextHref || bookDetailHref(book);
      if (href) {
        const ariaLabel = contextHref
          ? `${actionLabel}; preview includes ${title}`
          : `Open book details for ${title}`;
        return `
          <a
            class="cover-preview-button"
            href="${escapeHtml(href)}"
            title="${escapeHtml(title)}"
            aria-label="${escapeHtml(ariaLabel)}"
          >
            <span
              class="cover-preview-cover"
              data-cover-url="${escapeHtml(coverUrl)}"
              data-cover-title="${escapeHtml(title)}"
            ></span>
          </a>
        `.trim();
      }

      const ariaLabel = `${actionLabel}; preview includes ${title}`;
      return `
        <button
          class="cover-preview-button"
          type="button"
          title="${escapeHtml(title)}"
          aria-label="${escapeHtml(ariaLabel)}"
          data-action="${escapeHtml(action)}"
          data-id="${escapeHtml(contextId)}"
          data-name="${escapeHtml(contextName)}"
        >
          <span
            class="cover-preview-cover"
            data-cover-url="${escapeHtml(coverUrl)}"
            data-cover-title="${escapeHtml(title)}"
          ></span>
        </button>
      `.trim();
    })
    .join("");

  return `<div class="cover-preview-strip" aria-label="${escapeHtml(actionLabel)} previews">${buttons}</div>`;
}
