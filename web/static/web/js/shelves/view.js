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

const DEFAULT_PAGE_SIZE = 20;
const PAGE_SIZE_OPTIONS = new Set([20, 30, 40, 50]);

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

  const article = el("article", "library-row");
  const cover = el("div", "book__cover");
  cover.dataset.coverUrl = coverUrl;
  cover.dataset.coverTitle = title;
  article.appendChild(cover);

  const content = el("div", "library-row__body");
  const heading = el("h3", "library-row__title");
  const link = el("a", "", title);
  link.href = `/library/books/${encodeURIComponent(bookId)}/`;
  heading.appendChild(link);
  content.appendChild(heading);

  const metadata = el("div", "library-row__meta book-metadata");
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

  const tags = Array.isArray(book.tags)
    ? book.tags.map((tag) => (tag && tag.name ? String(tag.name).trim() : "")).filter(Boolean)
    : [];
  if (tags.length) {
    const tagRow = el("div", "library-row__tags");
    tagRow.appendChild(el("span", "library-row__label", "Tags"));
    const tagList = el("span", "library-row__tag-list");
    tags.slice(0, 6).forEach((tag) => tagList.appendChild(el("span", "pill", tag)));
    if (tags.length > 6) tagList.appendChild(el("span", "pill", `+${tags.length - 6}`));
    tagRow.appendChild(tagList);
    content.appendChild(tagRow);
  }

  article.appendChild(content);
  return article;
}

function pageSize(value) {
  const parsed = Number.parseInt(String(value || ""), 10);
  return PAGE_SIZE_OPTIONS.has(parsed) ? parsed : DEFAULT_PAGE_SIZE;
}

export function shelfViewListState(search) {
  const params = new URLSearchParams(search || "");
  const parsedPage = Number.parseInt(params.get("page") || "1", 10);
  return {
    page: Number.isInteger(parsedPage) && parsedPage > 0 ? parsedPage : 1,
    pageSize: pageSize(params.get("page_size")),
    ordering: String(params.get("ordering") || ""),
  };
}

export function shelfViewBrowserHref(shelfId, state, search = "") {
  const params = new URLSearchParams(search || "");
  params.delete("page");
  params.delete("page_size");
  if (state.page > 1) params.set("page", String(state.page));
  if (state.pageSize !== DEFAULT_PAGE_SIZE) params.set("page_size", String(state.pageSize));
  if (state.ordering) params.set("ordering", state.ordering);
  const suffix = params.toString();
  return `/shelves/${encodeURIComponent(String(shelfId))}/${suffix ? `?${suffix}` : ""}`;
}

function shelfItemsApiUrl(shelfId, state) {
  const params = new URLSearchParams({ page_size: String(state.pageSize) });
  if (state.page > 1) params.set("page", String(state.page));
  if (state.ordering) params.set("ordering", state.ordering);
  return `/api/v1/shelves/${encodeURIComponent(String(shelfId))}/items/?${params.toString()}`;
}

function rangeText(payload, resultCount, state) {
  const count = Number(payload && payload.count) || 0;
  if (!count || !resultCount) return "Showing 0 of 0";
  const start = (state.page - 1) * state.pageSize + 1;
  return `Showing ${start}-${Math.min(count, start + resultCount - 1)} of ${count}`;
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
  const prevButtons = [$("#shelf-view-items-prev-top"), $("#shelf-view-items-prev-bottom")].filter(Boolean);
  const nextButtons = [$("#shelf-view-items-next-top"), $("#shelf-view-items-next-bottom")].filter(Boolean);
  const pageSizeSelects = [$("#shelf-view-items-page-size-top"), $("#shelf-view-items-page-size-bottom")].filter(Boolean);
  const rangeEls = [$("#shelf-view-items-range-top"), $("#shelf-view-items-range-bottom")].filter(Boolean);
  const pagers = [$("#shelf-view-items-pager-top"), $("#shelf-view-items-pager-bottom")].filter(Boolean);
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
    prevButtons.length !== 2 ||
    nextButtons.length !== 2 ||
    pageSizeSelects.length !== 2 ||
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

    let state = shelfViewListState(window.location.search);
    let nextUrl = null;
    let prevUrl = null;
    window.history.replaceState({}, "", shelfViewBrowserHref(shelfId, state, window.location.search));

    async function loadItems(nextState, { history = "none" } = {}) {
      state = nextState;
      setStatus(itemsStatus, "Loading...", false);
      const payload = await fetchJSON(shelfItemsApiUrl(shelfId, state));
      renderShelfItems(itemsResults, payload);
      mountCovers(itemsResults);
      nextUrl = payload && payload.next ? String(payload.next) : null;
      prevUrl = payload && payload.previous ? String(payload.previous) : null;
      prevButtons.forEach((button) => { button.disabled = !prevUrl; });
      nextButtons.forEach((button) => { button.disabled = !nextUrl; });
      pageSizeSelects.forEach((select) => { select.value = String(state.pageSize); });
      const rows = Array.isArray(payload && payload.results) ? payload.results : [];
      const range = rangeText(payload, rows.length, state);
      rangeEls.forEach((element) => { element.textContent = range; });
      pagers.forEach((pager) => pager.classList.toggle("is-hidden", !(payload && payload.count)));
      if (history === "push") {
        window.history.pushState({}, "", shelfViewBrowserHref(shelfId, state, window.location.search));
      }
      visible(itemsWrap, true);
      setStatus(itemsStatus, "", false);
    }

    prevButtons.forEach((button) => button.addEventListener("click", () => {
      if (!prevUrl || state.page <= 1) return;
      loadItems({ ...state, page: state.page - 1 }, { history: "push" }).catch((error) => setGlobalError(extractApiErrorMessage(error)));
    }));
    nextButtons.forEach((button) => button.addEventListener("click", () => {
      if (!nextUrl) return;
      loadItems({ ...state, page: state.page + 1 }, { history: "push" }).catch((error) => setGlobalError(extractApiErrorMessage(error)));
    }));
    pageSizeSelects.forEach((select) => select.addEventListener("change", () => {
      const nextPageSize = pageSize(select.value);
      if (nextPageSize === state.pageSize) return;
      loadItems({ ...state, page: 1, pageSize: nextPageSize }, { history: "push" }).catch((error) => setGlobalError(extractApiErrorMessage(error)));
    }));
    window.addEventListener("popstate", () => {
      loadItems(shelfViewListState(window.location.search)).catch((error) => setGlobalError(extractApiErrorMessage(error)));
    });

    await loadItems(state);
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
