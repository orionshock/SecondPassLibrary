import { $, escapeHtml, loadMeAndInitShell, setGlobalError } from "../layout.js";
import { renderCoverPreviewStrip } from "../ui/cover_previews.js";
import { createPagedListController } from "../ui/paged_list.js";
import { shelfMetadataLine } from "./shared.js";

function renderShelfRow(shelf) {
  const id = shelf && shelf.id != null ? String(shelf.id) : "";
  const name = shelf && shelf.name ? String(shelf.name) : "(Unnamed shelf)";
  const description = shelf && shelf.description ? String(shelf.description) : "";
  const metadata = shelfMetadataLine(shelf);
  const href = `/shelves/${encodeURIComponent(id)}/`;
  const previews = renderCoverPreviewStrip(shelf.preview_books, {
    actionLabel: `View shelf ${name}`,
  });

  return `
    <article class="book shelf-list-card" data-shelf-url="${escapeHtml(href)}">
      <div class="shelf-list-card__main">
        <h3 class="book__title shelf-list-card__title">
          <a href="${escapeHtml(href)}" title="Open shelf ${escapeHtml(name)}">${escapeHtml(name)}</a>
        </h3>
        ${description ? `<div class="muted shelf-list-card__description">${escapeHtml(description)}</div>` : ""}
        ${metadata ? `<div class="muted shelf-list-card__metadata">${metadata}</div>` : ""}
      </div>
      ${previews}
    </article>
  `.trim();
}

function isInteractiveElement(element) {
  return !!element.closest("a, button, input, select, textarea, label, summary, [role='button'], [role='link']");
}

function installShelfCardNavigation(root) {
  if (!root) return;
  root.addEventListener("click", (event) => {
    const source = event.target;
    if (!(source instanceof Element)) return;
    if (isInteractiveElement(source)) return;

    const card = source.closest("[data-shelf-url]");
    const url = card && card.getAttribute("data-shelf-url");
    if (url) window.location.assign(url);
  });
}

function renderShelfRows(_payload, rows, emptyText) {
  if (!rows.length) return `<div class="muted">${escapeHtml(emptyText)}</div>`;
  return rows.map(renderShelfRow).join("");
}

const SHELF_SCOPES = new Set(["personal", "shared", "group"]);
const DEFAULT_PAGE_SIZE = 20;
const PAGE_SIZE_OPTIONS = new Set([20, 30, 40, 50]);

function positiveInt(value, fallback) {
  const parsed = Number.parseInt(String(value || ""), 10);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

function pageSize(value) {
  const parsed = positiveInt(value, DEFAULT_PAGE_SIZE);
  return PAGE_SIZE_OPTIONS.has(parsed) ? parsed : DEFAULT_PAGE_SIZE;
}

function rangeText(payload, rows, state) {
  const count = Number(payload && payload.count) || 0;
  if (!count || !rows.length) return "Showing 0 of 0";
  const start = (state.page - 1) * state.pageSize + 1;
  return `Showing ${start}-${Math.min(count, start + rows.length - 1)} of ${count}`;
}

export function shelfListState(search) {
  const params = new URLSearchParams(search || "");
  const requestedScope = String(params.get("scope") || "").toLowerCase();
  const scope = SHELF_SCOPES.has(requestedScope) ? requestedScope : "personal";
  const rawPage = Number.parseInt(params.get("page") || "1", 10);
  const page = Number.isInteger(rawPage) && rawPage > 0 ? rawPage : 1;
  return { scope, page, pageSize: pageSize(params.get("page_size")) };
}

export function shelfListBrowserHref(scope, page = 1, selectedPageSize = DEFAULT_PAGE_SIZE, search = "") {
  const state = shelfListState(`?scope=${encodeURIComponent(String(scope || ""))}&page=${page}&page_size=${selectedPageSize}`);
  const params = new URLSearchParams(search || "");
  params.set("scope", state.scope);
  params.delete("page");
  params.delete("page_size");
  if (state.page > 1) params.set("page", String(state.page));
  if (state.pageSize !== DEFAULT_PAGE_SIZE) params.set("page_size", String(state.pageSize));
  return `/shelves/?${params.toString()}`;
}

export function shelfListApiUrl(scope, page = 1, selectedPageSize = DEFAULT_PAGE_SIZE) {
  const state = shelfListState(`?scope=${encodeURIComponent(String(scope || ""))}&page=${page}&page_size=${selectedPageSize}`);
  const params = new URLSearchParams({
    scope: state.scope,
    include_preview_books: "true",
    page_size: String(state.pageSize),
  });
  if (state.page > 1) params.set("page", String(state.page));
  return `/api/v1/shelves/?${params.toString()}`;
}

export function shelfEmptyText(scope) {
  if (scope === "shared") return "No shared shelves from other users.";
  if (scope === "group") return "No group shelves.";
  return "No personal shelves.";
}

function stateFromApiUrl(url, scope) {
  const parsed = new URL(url, window.location.origin);
  const parsedState = shelfListState(parsed.search);
  return { scope, page: parsedState.page, pageSize: parsedState.pageSize };
}

function setSelectedScope(tabs, scope) {
  for (const tab of tabs) {
    const selected = tab.dataset.shelfScope === scope;
    tab.classList.toggle("is-active", selected);
    tab.setAttribute("aria-selected", selected ? "true" : "false");
  }
}

export async function initShelvesList() {
  await loadMeAndInitShell();
  setGlobalError("");

  const statusEl = $("#shelves-status");
  const resultsEl = $("#shelves-results");
  const prevButtons = [$("#shelves-prev-top"), $("#shelves-prev-bottom")];
  const nextButtons = [$("#shelves-next-top"), $("#shelves-next-bottom")];
  const pageSizeSelects = [$("#shelves-page-size-top"), $("#shelves-page-size-bottom")];
  const rangeEls = [$("#shelves-range-top"), $("#shelves-range-bottom")];
  const pagers = [$("#shelves-pager-top"), $("#shelves-pager-bottom")];
  const tabs = Array.from(document.querySelectorAll("[data-shelf-scope]"));
  if (!statusEl || !resultsEl || [...prevButtons, ...nextButtons, ...pageSizeSelects, ...rangeEls, ...pagers].some((element) => !element) || !tabs.length) return;

  installShelfCardNavigation(resultsEl);
  let state = shelfListState(window.location.search);
  setSelectedScope(tabs, state.scope);
  window.history.replaceState({}, "", shelfListBrowserHref(state.scope, state.page, state.pageSize, window.location.search));

  function syncPager(payload, rows) {
    const text = rangeText(payload, rows, state);
    rangeEls.forEach((element) => { element.textContent = text; });
    pageSizeSelects.forEach((select) => { select.value = String(state.pageSize); });
    prevButtons[0].disabled = prevButtons[1].disabled;
    nextButtons[0].disabled = nextButtons[1].disabled;
    pagers.forEach((pager) => pager.classList.toggle("is-hidden", !(payload && payload.count)));
  }

  const controller = await createPagedListController({
    statusEl,
    resultsEl,
    prevBtn: prevButtons[1],
    nextBtn: nextButtons[1],
    initialUrl: shelfListApiUrl(state.scope, state.page, state.pageSize),
    emptyText: shelfEmptyText(state.scope),
    autoLoad: false,
    clearResultsOnLoad: false,
    render: (payload, rows) => renderShelfRows(payload, rows, shelfEmptyText(state.scope)),
    formatStatus: () => "",
    onLoaded: (_payload, _rows, { url, reason }) => {
      state = stateFromApiUrl(url, state.scope);
      syncPager(_payload, _rows);
      if (reason === "next" || reason === "previous") {
        window.history.pushState({}, "", shelfListBrowserHref(state.scope, state.page, state.pageSize, window.location.search));
      }
    },
  });

  async function loadState(nextState, { history = "none", reason = "load" } = {}) {
    state = nextState;
    setSelectedScope(tabs, state.scope);
    if (history === "push") {
      window.history.pushState({}, "", shelfListBrowserHref(state.scope, state.page, state.pageSize, window.location.search));
    }
    await controller.load(shelfListApiUrl(state.scope, state.page, state.pageSize), { reason });
  }

  prevButtons[0].addEventListener("click", () => prevButtons[1].click());
  nextButtons[0].addEventListener("click", () => nextButtons[1].click());
  pageSizeSelects.forEach((select) => {
    select.addEventListener("change", async () => {
      const nextPageSize = pageSize(select.value);
      if (nextPageSize === state.pageSize) return;
      await loadState({ ...state, page: 1, pageSize: nextPageSize }, { history: "push", reason: "page-size" });
    });
  });

  for (const tab of tabs) {
    tab.addEventListener("click", async () => {
      const scope = shelfListState(`?scope=${tab.dataset.shelfScope || ""}`).scope;
      if (scope === state.scope) return;
      await loadState({ scope, page: 1, pageSize: state.pageSize }, { history: "push", reason: "scope" });
    });
  }

  window.addEventListener("popstate", async () => {
    await loadState(shelfListState(window.location.search), { reason: "popstate" });
  });

  await loadState(state);
}
