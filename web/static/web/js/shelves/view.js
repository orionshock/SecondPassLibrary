import { extractApiErrorMessage, fetchJSON } from "../api.js";
import { $, loadMeAndInitShell, setGlobalError, visible } from "../layout.js";
import { setStatus } from "../ui/status.js";
import { syncShelfBreadcrumb } from "./navigation.js";
import {
  inferCanEditShelf,
  renderShelfMetadata,
  shelfCreatedByDisplay,
} from "./shared.js";
import { mountCovers } from "../ui/covers.js";
import { bookMetadataItems } from "../ui/book_metadata.js";

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function renderShelfItem(item) {
  const book = item && item.book ? item.book : {};
  const bookId = book.id ? String(book.id) : "";
  const title = book.title ? String(book.title) : "(Untitled)";
  const coverUrl = book.cover_url ? String(book.cover_url) : "";

  const article = el("article", "book book--with-cover");
  const cover = el("div", "book__cover");
  cover.dataset.coverUrl = coverUrl;
  cover.dataset.coverTitle = title;
  article.appendChild(cover);

  const content = document.createElement("div");
  const heading = el("h3", "book__title");
  const link = el("a", "", title);
  link.href = `/library/books/${encodeURIComponent(bookId)}/`;
  heading.appendChild(link);
  content.appendChild(heading);

  const metadata = el("div", "muted book-metadata");
  for (const item of bookMetadataItems(book)) {
    const group = el("span", "book-metadata__item");
    const icon = el("span", "material-symbols-outlined book-metadata__icon", item.icon);
    icon.setAttribute("aria-hidden", "true");
    group.appendChild(icon);
    const label = el("span", "sr-only", `${item.label}: `);
    group.appendChild(label);
    group.appendChild(el("span", "book-metadata__value", item.value));
    metadata.appendChild(group);
  }
  if (metadata.childNodes.length) content.appendChild(metadata);

  article.appendChild(content);
  return article;
}

function renderShelfItems(container, payload) {
  const results = Array.isArray(payload && payload.results) ? payload.results : [];
  container.replaceChildren();
  if (!results.length) {
    container.appendChild(el("div", "muted", "No visible books."));
    return;
  }

  const fragment = document.createDocumentFragment();
  results.forEach((item) => fragment.appendChild(renderShelfItem(item)));
  container.appendChild(fragment);
}

export async function initShelfView() {
  const me = await loadMeAndInitShell();
  setGlobalError("");

  const statusEl = $("#shelf-view-status");
  const errEl = $("#shelf-view-error");
  const wrapEl = $("#shelf-view");
  const summaryEl = $("#shelf-view-summary");
  const descriptionEl = $("#shelf-view-description");
  const createdByEl = $("#shelf-view-created-by");
  const itemsWrap = $("#shelf-view-items");
  const itemsStatus = $("#shelf-view-items-status");
  const itemsResults = $("#shelf-view-items-results");
  const prevBtn = $("#shelf-view-items-prev");
  const nextBtn = $("#shelf-view-items-next");
  const noteEl = $("#shelf-view-items-page-note");
  const titleEl = $("#shelf-title");
  const editWrap = $("#shelf-view-edit-wrap");
  const editLink = $("#shelf-view-edit-link");
  if (
    !statusEl ||
    !errEl ||
    !wrapEl ||
    !summaryEl ||
    !descriptionEl ||
    !createdByEl ||
    !itemsWrap ||
    !itemsStatus ||
    !itemsResults ||
    !prevBtn ||
    !nextBtn ||
    !noteEl ||
    !titleEl ||
    !editWrap ||
    !editLink
  ) {
    return;
  }

  function setErr(message) {
    errEl.textContent = message || "";
    visible(errEl, !!message);
  }

  const shelfId = wrapEl.dataset ? wrapEl.dataset.shelfId : "";
  if (!shelfId) {
    setStatus(statusEl, "Missing shelf id.", true);
    return;
  }
  syncShelfBreadcrumb({ shelfName: "Shelf" });

  setStatus(statusEl, "Loading...", false);
  setErr("");
  visible(wrapEl, false);
  visible(itemsWrap, false);
  visible(editWrap, false);

  try {
    const shelf = await fetchJSON(`/api/v1/shelves/${encodeURIComponent(String(shelfId))}/`);
    titleEl.textContent = shelf && shelf.name ? String(shelf.name) : "Shelf";
    syncShelfBreadcrumb({ shelfName: shelf.name || "Shelf" });
    summaryEl.replaceChildren(
      renderShelfMetadata(shelf, { includeVisibility: false })
    );

    const description = shelf && shelf.description ? String(shelf.description).trim() : "";
    descriptionEl.textContent = description;
    visible(descriptionEl, !!description);

    const createdBy = shelfCreatedByDisplay(shelf);
    createdByEl.textContent = createdBy;
    visible(createdByEl, !!createdBy);
    visible(wrapEl, !!description || !!createdBy);

    const canEdit =
      shelf && shelf.can_edit != null
        ? !!shelf.can_edit
        : inferCanEditShelf({ me, shelf });
    visible(editWrap, canEdit);
    if (canEdit) {
      editLink.setAttribute(
        "href",
        `/shelves/${encodeURIComponent(String(shelfId))}/edit/`
      );
    }

    let nextUrl = null;
    let prevUrl = null;
    let currentUrl = `/api/v1/shelves/${encodeURIComponent(String(shelfId))}/items/`;

    async function loadItems(url) {
      setStatus(itemsStatus, "Loading...", false);
      const payload = await fetchJSON(url);
      renderShelfItems(itemsResults, payload);
      mountCovers(itemsResults);
      nextUrl = payload && payload.next ? String(payload.next) : null;
      prevUrl = payload && payload.previous ? String(payload.previous) : null;
      prevBtn.disabled = !prevUrl;
      nextBtn.disabled = !nextUrl;
      noteEl.textContent = payload && payload.count != null ? `${payload.count} total` : "";
      visible(itemsWrap, true);
      setStatus(itemsStatus, "", false);
    }

    prevBtn.addEventListener("click", () => {
      if (!prevUrl) return;
      currentUrl = prevUrl;
      loadItems(currentUrl).catch((error) =>
        setGlobalError(extractApiErrorMessage(error))
      );
    });
    nextBtn.addEventListener("click", () => {
      if (!nextUrl) return;
      currentUrl = nextUrl;
      loadItems(currentUrl).catch((error) =>
        setGlobalError(extractApiErrorMessage(error))
      );
    });

    await loadItems(currentUrl);
    setStatus(statusEl, "", false);
  } catch (error) {
    console.error("Failed to load shelf view", { shelfId, error });
    const message =
      error && error.status === 404
        ? "Shelf not found or not accessible."
        : extractApiErrorMessage(error);
    setErr(message);
    setStatus(statusEl, "Error.", true);
    setGlobalError(message);
  }
}
