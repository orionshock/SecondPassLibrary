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

function pageNote(payload, rows) {
  if (!payload || payload.count == null) return "";
  return `Showing ${rows.length} of ${Number(payload.count)}.`;
}

const SHELF_SCOPES = new Set(["personal", "shared", "group"]);

export function shelfListState(search) {
  const params = new URLSearchParams(search || "");
  const requestedScope = String(params.get("scope") || "").toLowerCase();
  const scope = SHELF_SCOPES.has(requestedScope) ? requestedScope : "personal";
  const rawPage = Number.parseInt(params.get("page") || "1", 10);
  const page = Number.isInteger(rawPage) && rawPage > 0 ? rawPage : 1;
  return { scope, page };
}

export function shelfListBrowserHref(scope, page = 1, search = "") {
  const state = shelfListState(`?scope=${encodeURIComponent(String(scope || ""))}&page=${page}`);
  const params = new URLSearchParams(search || "");
  params.set("scope", state.scope);
  params.delete("page");
  if (state.page > 1) params.set("page", String(state.page));
  return `/shelves/?${params.toString()}`;
}

export function shelfListApiUrl(scope, page = 1) {
  const state = shelfListState(`?scope=${encodeURIComponent(String(scope || ""))}&page=${page}`);
  const params = new URLSearchParams({
    scope: state.scope,
    include_preview_books: "true",
  });
  if (state.page > 1) params.set("page", String(state.page));
  return `/api/v1/shelves/?${params.toString()}`;
}

export function shelfEmptyText(scope) {
  if (scope === "shared") return "No shared shelves from other users.";
  if (scope === "group") return "No group shelves.";
  return "No personal shelves.";
}

function pageFromApiUrl(url) {
  const parsed = new URL(url, window.location.origin);
  return shelfListState(parsed.search).page;
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
  const prevBtn = $("#shelves-prev");
  const nextBtn = $("#shelves-next");
  const noteEl = $("#shelves-page-note");
  const tabs = Array.from(document.querySelectorAll("[data-shelf-scope]"));
  if (!statusEl || !resultsEl || !prevBtn || !nextBtn || !noteEl || !tabs.length) return;

  installShelfCardNavigation(resultsEl);
  let state = shelfListState(window.location.search);
  setSelectedScope(tabs, state.scope);
  window.history.replaceState({}, "", shelfListBrowserHref(state.scope, state.page, window.location.search));

  const controller = await createPagedListController({
    statusEl,
    resultsEl,
    prevBtn,
    nextBtn,
    noteEl,
    initialUrl: shelfListApiUrl(state.scope, state.page),
    emptyText: shelfEmptyText(state.scope),
    autoLoad: false,
    clearResultsOnLoad: false,
    render: (payload, rows) => renderShelfRows(payload, rows, shelfEmptyText(state.scope)),
    formatStatus: () => "",
    formatNote: pageNote,
    onLoaded: (_payload, _rows, { url, reason }) => {
      state = { ...state, page: pageFromApiUrl(url) };
      if (reason === "next" || reason === "previous") {
        window.history.pushState({}, "", shelfListBrowserHref(state.scope, state.page, window.location.search));
      }
    },
  });

  async function loadState(nextState, { history = "none", reason = "load" } = {}) {
    state = nextState;
    setSelectedScope(tabs, state.scope);
    if (history === "push") {
      window.history.pushState({}, "", shelfListBrowserHref(state.scope, state.page, window.location.search));
    }
    await controller.load(shelfListApiUrl(state.scope, state.page), { reason });
  }

  for (const tab of tabs) {
    tab.addEventListener("click", async () => {
      const scope = shelfListState(`?scope=${tab.dataset.shelfScope || ""}`).scope;
      if (scope === state.scope) return;
      await loadState({ scope, page: 1 }, { history: "push", reason: "scope" });
    });
  }

  window.addEventListener("popstate", async () => {
    await loadState(shelfListState(window.location.search), { reason: "popstate" });
  });

  await loadState(state);
}
