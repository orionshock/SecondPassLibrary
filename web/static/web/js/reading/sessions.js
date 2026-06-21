import { fetchJSON } from "../api.js";
import {
  $,
  loadMeAndInitShell,
  setGlobalErrorFromError,
  visible,
} from "../layout.js";
import { mountCovers } from "../ui/covers.js";
import { setStatus } from "../ui/status.js";

const DEFAULT_PAGE_SIZE = 20;
const PAGE_SIZE_OPTIONS = new Set(["10", "20", "50"]);
const STATUS_FILTERS = new Set(["all", "active", "closed"]);

function formatWhen(value) {
  if (!value) return "";
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function normalizeStatusFilter(params) {
  const status = (params.get("status") || "").trim().toLowerCase();
  if (STATUS_FILTERS.has(status)) return status;

  const isActive = (params.get("is_active") || "").trim().toLowerCase();
  if (isActive === "true") return "active";
  if (isActive === "false") return "closed";
  return "all";
}

function readQueryState() {
  const params = new URLSearchParams(window.location.search);
  const rawPageSize = (params.get("page_size") || "").trim();
  return {
    book: (params.get("book") || "").trim(),
    q: (params.get("q") || "").trim(),
    status: normalizeStatusFilter(params),
    pageSize: PAGE_SIZE_OPTIONS.has(rawPageSize) ? Number(rawPageSize) : DEFAULT_PAGE_SIZE,
  };
}

function buildApiUrl(state) {
  const url = new URL("/api/v1/reading/sessions/", window.location.origin);
  if (state.book) url.searchParams.set("book", state.book);
  if (state.q) url.searchParams.set("q", state.q);
  if (state.status === "active") url.searchParams.set("is_active", "true");
  if (state.status === "closed") url.searchParams.set("is_active", "false");
  url.searchParams.set("page_size", String(state.pageSize));
  return url.toString();
}

function writeQueryState(state, { replace = false } = {}) {
  const url = new URL(window.location.href);
  const params = new URLSearchParams();
  if (state.book) params.set("book", state.book);
  if (state.q) params.set("q", state.q);
  if (state.status !== "all") params.set("status", state.status);
  if (state.pageSize !== DEFAULT_PAGE_SIZE) params.set("page_size", String(state.pageSize));
  url.search = params.toString();
  window.history[replace ? "replaceState" : "pushState"]({}, "", url.toString());
}

function authorNames(book) {
  if (!Array.isArray(book && book.authors)) return [];
  return book.authors
    .map((author) => (author && typeof author === "object" ? author.name : author))
    .filter(Boolean)
    .map(String);
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function appendSeparatedParts(container, parts) {
  const values = parts
    .filter((part) => part !== null && part !== undefined)
    .map((part) => String(part).trim())
    .filter(Boolean);

  values.forEach((part) => {
    container.appendChild(el("span", "metadata-piece", part));
  });
}

function sessionCardTitle(session, bookTitle) {
  const name = session && typeof session.name === "string" ? session.name.trim() : "";
  return name || bookTitle;
}

function seriesLabel(book) {
  const name = book && book.series && book.series.name ? String(book.series.name).trim() : "";
  const index =
    book && book.series_index != null && book.series_index !== ""
      ? String(book.series_index).trim()
      : "";
  if (!name) return "";
  return index ? `${name} ${index}` : name;
}

function sessionActionLink({ href, icon, label }) {
  const link = el("a", "icon-button sessions-card__action");
  link.href = href;
  link.setAttribute("aria-label", label);
  link.setAttribute("title", label);
  const iconEl = el("span", "material-symbols-outlined", icon);
  iconEl.setAttribute("aria-hidden", "true");
  link.appendChild(iconEl);
  return link;
}

function renderSessionCard(session) {
  const book = session && session.book && typeof session.book === "object" ? session.book : {};
  const bookId = String((book && book.id) || (session && session.book_id) || "");
  const sessionId = String((session && session.id) || "");
  const bookTitle = String((book && book.title) || "Book");
  const authors = authorNames(book);
  const coverUrl = book && book.cover_url ? String(book.cover_url) : "";
  const completedAt = session && session.completed_at ? formatWhen(session.completed_at) : "";
  const updatedAt = session && session.updated_at ? formatWhen(session.updated_at) : "";
  const startedAt = session && session.started_at ? formatWhen(session.started_at) : "";
  const annotationCount = Number.isFinite(Number(session && session.annotation_count))
    ? Number(session.annotation_count)
    : 0;
  const progression = session && session.progression != null ? Number(session.progression) : null;
  const progressionText =
    progression != null && Number.isFinite(progression)
      ? `${Math.round(progression * 1000) / 10}%`
      : "Not available";
  const marginaliaHref =
    `/reading/sessions/books/${encodeURIComponent(bookId)}/${encodeURIComponent(sessionId)}/`;
  const bookSessionsHref = `/reading/sessions/?book=${encodeURIComponent(bookId)}`;

  const card = el("div", "card sessions-row sessions-card");

  const coverLink = el("a", "sessions-card__cover-link");
  coverLink.href = marginaliaHref;
  coverLink.setAttribute("aria-label", "Open session");
  const cover = el("div", "sessions-cover");
  cover.dataset.coverUrl = coverUrl;
  cover.dataset.coverTitle = bookTitle;
  cover.setAttribute("aria-hidden", "true");
  coverLink.appendChild(cover);
  card.appendChild(coverLink);

  const main = el("div", "sessions-row__main");
  const titleLink = el("a", "sessions-card__title", sessionCardTitle(session, bookTitle));
  titleLink.href = marginaliaHref;
  main.appendChild(titleLink);

  const bookMeta = el("div", "muted sessions-card__metadata");
  appendSeparatedParts(bookMeta, [bookTitle, authors.join(", "), seriesLabel(book)]);
  main.appendChild(bookMeta);
  main.appendChild(el("div", "muted sessions-row__id", sessionId));

  const dates = el("div", "muted sessions-card__metadata");
  appendSeparatedParts(dates, [
    startedAt ? `Started: ${startedAt}` : "",
    completedAt ? `Closed: ${completedAt}` : updatedAt ? `Updated: ${updatedAt}` : "",
  ]);
  main.appendChild(dates);

  const stats = el("div", "muted sessions-card__metadata");
  appendSeparatedParts(stats, [
    `Annotations: ${annotationCount}`,
    `Progression: ${progressionText}`,
  ]);
  main.appendChild(stats);
  card.appendChild(main);

  const trailing = el("div", "sessions-card__trailing");
  trailing.appendChild(
    el("span", "pill sessions-card__status", session && session.is_active ? "Active" : "Closed")
  );
  const actions = el("div", "sessions-card__actions");
  actions.appendChild(
    sessionActionLink({
      href: marginaliaHref,
      icon: "open_in_new",
      label: "Open session",
    })
  );
  actions.appendChild(
    sessionActionLink({
      href: bookSessionsHref,
      icon: "auto_stories",
      label: "View sessions for this book",
    })
  );
  trailing.appendChild(actions);
  card.appendChild(trailing);

  return card;
}

function contextBook(payload) {
  const context =
    payload && payload.context && typeof payload.context === "object" ? payload.context : null;
  return context && context.book && typeof context.book === "object" ? context.book : null;
}

function renderResults(container, payload, results, state) {
  container.replaceChildren();
  if (results.length) {
    const fragment = document.createDocumentFragment();
    results.forEach((session) => fragment.appendChild(renderSessionCard(session)));
    container.appendChild(fragment);
    return;
  }

  const empty = el("div", "muted");
  empty.id = "reading-sessions-all-empty";
  const book = contextBook(payload);
  empty.textContent =
    state.book && book && book.title
      ? `No reading sessions for ${String(book.title)} yet.`
      : "No reading sessions yet.";
  container.appendChild(empty);
}

export async function initReadingSessions() {
  await loadMeAndInitShell();

  const root = $("#reading-sessions-all");
  const subtitleEl = $("#reading-sessions-subtitle");
  const filtersEl = $("#reading-sessions-status-filters");
  const searchForm = $("#reading-sessions-search-form");
  const searchInput = $("#reading-sessions-search");
  const pageSizeSelect = $("#reading-sessions-page-size");
  const statusEl = $("#reading-sessions-status");
  const resultsEl = $("#reading-sessions-results");
  const prevBtn = $("#reading-sessions-prev");
  const nextBtn = $("#reading-sessions-next");

  if (
    !root ||
    !subtitleEl ||
    !filtersEl ||
    !searchForm ||
    !searchInput ||
    !pageSizeSelect ||
    !statusEl ||
    !resultsEl ||
    !prevBtn ||
    !nextBtn
  ) {
    return;
  }

  let state = readQueryState();
  let nextUrl = null;
  let previousUrl = null;

  function applyStateToControls() {
    searchInput.value = state.q;
    pageSizeSelect.value = String(state.pageSize);
    for (const button of filtersEl.querySelectorAll("[data-status-filter]")) {
      const active = button.dataset.statusFilter === state.status;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    }
  }

  async function load(url) {
    root.setAttribute("aria-busy", "true");
    setStatus(statusEl, "Loading sessions...", false);
    resultsEl.replaceChildren();
    prevBtn.disabled = true;
    nextBtn.disabled = true;

    try {
      const payload = await fetchJSON(url);
      const results = Array.isArray(payload && payload.results) ? payload.results : [];
      const book = contextBook(payload);

      subtitleEl.textContent =
        state.book && book && book.title ? `Reading sessions for ${String(book.title)}` : "";
      visible(subtitleEl, !!subtitleEl.textContent);
      renderResults(resultsEl, payload, results, state);
      mountCovers(resultsEl);

      nextUrl = payload && payload.next ? String(payload.next) : null;
      previousUrl = payload && payload.previous ? String(payload.previous) : null;
      nextBtn.disabled = !nextUrl;
      prevBtn.disabled = !previousUrl;

      const count = payload && payload.count != null ? Number(payload.count) : results.length;
      setStatus(statusEl, count ? `Showing ${results.length} of ${count} sessions.` : "", false);
    } catch (error) {
      console.error("Failed to load reading sessions", { url, error });
      const errorEl = el("div", "muted error", "Could not load reading sessions.");
      resultsEl.replaceChildren(errorEl);
      subtitleEl.textContent = "";
      visible(subtitleEl, false);
      setStatus(statusEl, "Error loading sessions.", true);
      setGlobalErrorFromError(error, "Failed to load reading sessions:");
      nextUrl = null;
      previousUrl = null;
    } finally {
      root.setAttribute("aria-busy", "false");
    }
  }

  async function reloadFirstPage({ replace = false } = {}) {
    writeQueryState(state, { replace });
    applyStateToControls();
    await load(buildApiUrl(state));
  }

  filtersEl.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-status-filter]");
    if (!button) return;
    const nextStatus = button.dataset.statusFilter || "all";
    if (!STATUS_FILTERS.has(nextStatus) || nextStatus === state.status) return;
    state = { ...state, status: nextStatus };
    await reloadFirstPage();
  });

  searchForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    state = { ...state, q: (searchInput.value || "").trim() };
    await reloadFirstPage();
  });

  pageSizeSelect.addEventListener("change", async () => {
    const value = String(pageSizeSelect.value || "");
    state = {
      ...state,
      pageSize: PAGE_SIZE_OPTIONS.has(value) ? Number(value) : DEFAULT_PAGE_SIZE,
    };
    await reloadFirstPage();
  });

  prevBtn.addEventListener("click", async () => {
    if (previousUrl) await load(previousUrl);
  });
  nextBtn.addEventListener("click", async () => {
    if (nextUrl) await load(nextUrl);
  });

  window.addEventListener("popstate", async () => {
    state = readQueryState();
    applyStateToControls();
    await load(buildApiUrl(state));
  });

  applyStateToControls();
  await reloadFirstPage({ replace: true });
}
