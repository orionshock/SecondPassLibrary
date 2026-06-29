import { fetchJSON } from "../api.js";
import { $, escapeHtml, loadMeAndInitShell, setGlobalErrorFromError } from "../layout.js";
import { renderCoverPreviewStrip } from "../ui/cover_previews.js";
import { mountCovers } from "../ui/covers.js";
import { renderGroupBadge } from "../ui/groups.js";
import { setStatus } from "../ui/status.js";
import { renderContextProseBlock, toggleProseBlock } from "./prose.js";

const DEFAULT_PAGE_SIZE = 20;
const PAGE_SIZE_OPTIONS = [20, 30, 40, 50];
const VIEWS = new Set(["books", "authors", "series"]);

function publishedYear(value) {
  const raw = value == null ? "" : String(value).trim();
  if (!raw) return "";
  const match = raw.match(/\d{4}/);
  return match ? match[0] : raw;
}

function compactSubtitle(title, subtitle) {
  const cleanSubtitle = subtitle ? String(subtitle).trim() : "";
  if (!cleanSubtitle) return "";
  const cleanTitle = title ? String(title).trim().toLowerCase() : "";
  return cleanTitle.includes(cleanSubtitle.toLowerCase()) ? "" : cleanSubtitle;
}

function renderTags(subjects) {
  const values = Array.isArray(subjects)
    ? subjects.map((s) => String(s).trim()).filter(Boolean)
    : typeof subjects === "string"
      ? [subjects.trim()].filter(Boolean)
      : [];
  if (!values.length) return "";

  const visible = values.slice(0, 6);
  const extra = values.length - visible.length;
  const pills = visible
    .map((tag) => `<span class="pill">${escapeHtml(tag)}</span>`)
    .join(" ");
  return `<div class="library-row__tags"><span class="library-row__label">Tags</span><span class="library-row__tag-list">${pills}${extra > 0 ? ` <span class="pill">+${extra}</span>` : ""}</span></div>`;
}

function renderGroups(groups) {
  const visibleGroups = Array.isArray(groups) ? groups : [];
  if (!visibleGroups.length) return "";
  const badges = visibleGroups
    .map((group) => renderGroupBadge(group, { compact: true }).outerHTML)
    .join(" ");
  return `<div class="library-row__groups">${badges}</div>`;
}

function parsePositiveInt(value, fallback) {
  const parsed = Number.parseInt(String(value || ""), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function pageSizeFromValue(value) {
  const parsed = parsePositiveInt(value, DEFAULT_PAGE_SIZE);
  return PAGE_SIZE_OPTIONS.includes(parsed) ? parsed : DEFAULT_PAGE_SIZE;
}

function rangeText({ count, page, pageSize, resultLength }) {
  if (!count || !resultLength) return "Showing 0 of 0";
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(count, start + resultLength - 1);
  return `Showing ${start}-${end} of ${count}`;
}

function visibleBookCountLabel(count) {
  const value = Number.isFinite(Number(count)) ? Number(count) : 0;
  return `${value} ${value === 1 ? "Book" : "Books"}`;
}

function renderBooks(payload) {
  const results = Array.isArray(payload && payload.results) ? payload.results : [];
  if (results.length === 0) return "";

  return results
    .map((b) => {
      const title = b.title || "(Untitled)";
      const bookHref = b.id ? `/library/books/${encodeURIComponent(String(b.id))}/` : null;
      const subtitle = compactSubtitle(title, b.subtitle);
      const authors = Array.isArray(b.authors) ? b.authors.map((a) => a.name).filter(Boolean) : [];
      const series = b.series && b.series.name ? b.series.name : "";
      const seriesIndex = b.series_index != null && b.series_index !== "" ? String(b.series_index) : "";
      const seriesLine = series ? `${series}${seriesIndex ? ` ${seriesIndex}` : ""}` : "";
      const coverUrl = b.cover_url ? String(b.cover_url) : "";
      const year = publishedYear(b.published_date);
      const publisher = b.publisher ? String(b.publisher).trim() : "";
      const publisherLine = [publisher, year].filter(Boolean).join(" - ");

      const metaLines = [];
      if (authors.length) metaLines.push(`<span>${escapeHtml(authors.join(", "))}</span>`);
      if (seriesLine) metaLines.push(`<span>${escapeHtml(seriesLine)}</span>`);
      if (publisherLine) metaLines.push(`<span>${escapeHtml(publisherLine)}</span>`);
      const tags = renderTags(b.subjects);
      const groups = renderGroups(b.groups);

      return `
          <article class="library-row">
            <div class="book__cover" data-cover-url="${escapeHtml(coverUrl)}" data-cover-title="${escapeHtml(title)}"></div>
            <div class="library-row__body">
              <h3 class="library-row__title">${
                bookHref
                  ? `<a href="${escapeHtml(bookHref)}">${escapeHtml(title)}</a>`
                  : `${escapeHtml(title)}`
              }</h3>
              ${subtitle ? `<div class="library-row__subtitle">${escapeHtml(subtitle)}</div>` : ""}
              <div class="library-row__meta">${metaLines.join("") || '<span class="muted">No metadata.</span>'}</div>
              ${tags}
              ${groups}
            </div>
          </article>
        `.trim();
    })
    .join("");
}

function renderAuthors(payload) {
  const results = Array.isArray(payload && payload.results) ? payload.results : [];
  if (results.length === 0) return "";

  return results
    .map((author) => {
      const id = author && author.id ? String(author.id) : "";
      const name = author && author.name ? String(author.name) : "Unknown author";
      const previews = renderCoverPreviewStrip(author.preview_books, {
        action: "browse-author",
        contextId: id,
        contextName: name,
        actionLabel: `View Books by ${name}`,
      });
      return `
        <article class="library-browse-row">
          <div class="library-browse-row__main">
            <button
              class="library-browse-row__primary"
              type="button"
              data-action="browse-author"
              data-id="${escapeHtml(id)}"
              data-name="${escapeHtml(name)}"
              title="View Books by ${escapeHtml(name)}"
              aria-label="View Books by ${escapeHtml(name)}"
            >
              <h3 class="library-browse-row__title">${escapeHtml(name)}</h3>
              <div class="library-browse-row__meta">${escapeHtml(visibleBookCountLabel(author.book_count))}</div>
            </button>
          </div>
          ${previews}
        </article>
      `.trim();
    })
    .join("");
}

function renderSeries(payload) {
  const results = Array.isArray(payload && payload.results) ? payload.results : [];
  if (results.length === 0) return "";

  return results
    .map((series) => {
      const id = series && series.id ? String(series.id) : "";
      const name = series && series.name ? String(series.name) : "Unknown series";
      const previews = renderCoverPreviewStrip(series.preview_books, {
        action: "browse-series",
        contextId: id,
        contextName: name,
        actionLabel: `View Books in ${name}`,
      });
      return `
        <article class="library-browse-row">
          <div class="library-browse-row__main">
            <button
              class="library-browse-row__primary"
              type="button"
              data-action="browse-series"
              data-id="${escapeHtml(id)}"
              data-name="${escapeHtml(name)}"
              title="View Books in ${escapeHtml(name)}"
              aria-label="View Books in ${escapeHtml(name)}"
            >
              <h3 class="library-browse-row__title">${escapeHtml(name)}</h3>
              <div class="library-browse-row__meta">${escapeHtml(visibleBookCountLabel(series.book_count))}</div>
            </button>
          </div>
          ${previews}
        </article>
      `.trim();
    })
    .join("");
}

function urlWithParams(base, params) {
  const url = new URL(base, window.location.origin);
  for (const [k, v] of Object.entries(params || {})) {
    if (v === null || v === undefined || v === "") continue;
    url.searchParams.set(k, String(v));
  }
  return url.toString();
}

export async function initLibraryBrowse() {
  await loadMeAndInitShell();

  const statusEl = $("#library-status");
  const filterSummaryEl = $("#library-filter-summary");
  const rangeEl = $("#library-range");
  const resultsEl = $("#library-results");
  const nextBtn = $("#next");
  const prevBtn = $("#prev");
  const form = $("#library-search");
  const qInput = $("#q");
  const pageSizeSelect = $("#library-page-size");
  const viewTabs = Array.from(document.querySelectorAll("[data-view]"));

  if (!statusEl || !filterSummaryEl || !rangeEl || !resultsEl || !nextBtn || !prevBtn || !form || !qInput || !pageSizeSelect) return;

  const state = {
    view: "books",
    q: "",
    page: 1,
    pageSize: DEFAULT_PAGE_SIZE,
    authorId: "",
    authorName: "",
    authorBiography: "",
    seriesId: "",
    seriesName: "",
    seriesSummary: "",
    contextKey: "",
    count: 0,
    resultLength: 0,
    hasNext: false,
    hasPrevious: false,
  };

  function activeFilter() {
    if (state.view !== "books") return null;
    if (state.authorId) {
      return {
        id: state.authorId,
        label: "Author",
        name: state.authorName || state.authorId,
        prose: state.authorBiography,
      };
    }
    if (state.seriesId) {
      return {
        id: state.seriesId,
        label: "Series",
        name: state.seriesName || state.seriesId,
        prose: state.seriesSummary,
      };
    }
    return null;
  }

  function renderFilterSummary(filter) {
    const idPrefix = filter.label.toLowerCase();
    const prose = renderContextProseBlock({
      text: filter.prose,
      idPrefix,
      itemId: filter.id,
    });
    return `
      <div class="library-context">
        <div class="library-context__header">
          <span>${escapeHtml(filter.label)}: <strong>${escapeHtml(filter.name)}</strong></span>
          <button class="button" type="button" data-action="clear-library-filter">Clear</button>
        </div>
        ${prose}
      </div>
    `.trim();
  }

  function syncControls() {
    qInput.value = state.q;
    pageSizeSelect.value = String(state.pageSize);
    rangeEl.textContent = rangeText(state);
    prevBtn.disabled = !state.hasPrevious;
    nextBtn.disabled = !state.hasNext;

    for (const tab of viewTabs) {
      const isActive = tab.dataset.view === state.view;
      tab.classList.toggle("is-active", isActive);
      tab.setAttribute("aria-selected", isActive ? "true" : "false");
    }

    const filter = activeFilter();
    if (!filter) {
      filterSummaryEl.innerHTML = "";
      filterSummaryEl.classList.add("is-hidden");
    } else {
      filterSummaryEl.classList.remove("is-hidden");
      filterSummaryEl.innerHTML = renderFilterSummary(filter);
    }
  }

  async function loadActiveFilterContext() {
    if (state.view !== "books" || (!state.authorId && !state.seriesId)) {
      state.authorBiography = "";
      state.seriesSummary = "";
      state.contextKey = "";
      return;
    }

    const kind = state.authorId ? "author" : "series";
    const id = state.authorId || state.seriesId;
    const key = `${kind}:${id}`;
    if (state.contextKey === key) return;

    state.contextKey = key;
    state.authorBiography = "";
    state.seriesSummary = "";

    try {
      const payload = await fetchJSON(`/api/v1/library/${kind === "author" ? "authors" : "series"}/${encodeURIComponent(id)}/`);
      if (kind === "author") {
        state.authorName = payload && payload.name ? String(payload.name) : state.authorName;
        state.authorBiography = payload && payload.biography ? String(payload.biography) : "";
      } else {
        state.seriesName = payload && payload.name ? String(payload.name) : state.seriesName;
        state.seriesSummary = payload && payload.summary ? String(payload.summary) : "";
      }
    } catch (e) {
      console.warn("Failed to load library context prose", { kind, id, e });
    }
  }

  function apiUrlForState() {
    if (state.view === "authors") {
      return urlWithParams("/api/v1/library/authors/", {
        include_preview_books: "true",
        page: state.page,
        page_size: state.pageSize,
      });
    }

    if (state.view === "series") {
      return urlWithParams("/api/v1/library/series/", {
        include_preview_books: "true",
        page: state.page,
        page_size: state.pageSize,
      });
    }

    return urlWithParams("/api/v1/library/books/", {
      q: state.q,
      page: state.page,
      page_size: state.pageSize,
      author: state.authorId,
      series: state.seriesId,
      ordering: state.seriesId ? "series_index" : "",
    });
  }

  function locationParamsForState() {
    const params = {
      view: state.view,
      page: state.page,
      page_size: state.pageSize,
    };
    if (state.view === "books") {
      if (state.q) params.q = state.q;
      if (state.authorId) params.author = state.authorId;
      if (state.authorName) params.author_name = state.authorName;
      if (state.seriesId) params.series = state.seriesId;
      if (state.seriesName) params.series_name = state.seriesName;
    }
    return params;
  }

  function renderPayload(payload) {
    if (state.view === "authors") return renderAuthors(payload);
    if (state.view === "series") return renderSeries(payload);
    return renderBooks(payload);
  }

  function emptyText() {
    if (state.view === "authors") return "No authors.";
    if (state.view === "series") return "No series.";
    return "Empty library.";
  }

  async function loadCurrentPage({ push = false, replace = false } = {}) {
    setStatus(statusEl, "Loading...", false);
    resultsEl.innerHTML = "";
    state.hasNext = false;
    state.hasPrevious = false;
    state.resultLength = 0;
    nextBtn.disabled = true;
    prevBtn.disabled = true;
    rangeEl.textContent = "Loading...";

    try {
      const url = apiUrlForState();
      const [payload] = await Promise.all([fetchJSON(url), loadActiveFilterContext()]);
      const results = Array.isArray(payload && payload.results) ? payload.results : [];
      state.count = Number.isFinite(Number(payload && payload.count)) ? Number(payload.count) : results.length;
      state.resultLength = results.length;
      state.hasNext = !!(payload && payload.next);
      state.hasPrevious = !!(payload && payload.previous);

      const maxPage = Math.max(1, Math.ceil(state.count / state.pageSize));
      if (state.page > maxPage) {
        state.page = maxPage;
        await loadCurrentPage({ replace: true });
        return;
      }

      const hasAny =
        state.count > 0 || results.length > 0;

      if (!hasAny) {
        setStatus(statusEl, emptyText(), false);
        syncControls();
        if (push || replace) pushLocation(locationParamsForState(), { replace });
        return;
      }

      setStatus(statusEl, "", false);
      resultsEl.innerHTML = renderPayload(payload);
      mountCovers(resultsEl);
      syncControls();
      if (push || replace) pushLocation(locationParamsForState(), { replace });
    } catch (e) {
      console.error("Failed to load library browse view", { view: state.view, url: apiUrlForState(), e });
      setStatus(statusEl, "Error loading data.", true);
      setGlobalErrorFromError(e, "Failed to load library:");
      state.hasNext = false;
      state.hasPrevious = false;
      syncControls();
    }
  }

  function syncStateFromLocation() {
    const params = new URLSearchParams(window.location.search);
    const view = (params.get("view") || "books").trim();
    state.view = VIEWS.has(view) ? view : "books";
    state.q = state.view === "books" ? (params.get("q") || "").trim() : "";
    state.page = parsePositiveInt(params.get("page"), 1);
    state.pageSize = pageSizeFromValue(params.get("page_size"));
    state.authorId = state.view === "books" ? (params.get("author") || "").trim() : "";
    state.authorName = state.authorId ? (params.get("author_name") || "").trim() : "";
    state.authorBiography = "";
    state.seriesId = state.view === "books" ? (params.get("series") || "").trim() : "";
    state.seriesName = state.seriesId ? (params.get("series_name") || "").trim() : "";
    state.seriesSummary = "";
    state.contextKey = "";
    if (state.authorId && state.seriesId) {
      state.seriesId = "";
      state.seriesName = "";
      state.seriesSummary = "";
    }
    syncControls();
  }

  function pushLocation(params, { replace = false } = {}) {
    const url = new URL(window.location.href);
    url.search = new URLSearchParams(params).toString();
    if (replace) {
      window.history.replaceState({}, "", url.toString());
    } else {
      window.history.pushState({}, "", url.toString());
    }
  }

  syncStateFromLocation();
  await loadCurrentPage({ replace: true });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    state.view = "books";
    state.q = (qInput.value || "").trim();
    state.authorId = "";
    state.authorName = "";
    state.authorBiography = "";
    state.seriesId = "";
    state.seriesName = "";
    state.seriesSummary = "";
    state.contextKey = "";
    state.page = 1;
    await loadCurrentPage({ push: true });
  });

  pageSizeSelect.addEventListener("change", async () => {
    state.pageSize = pageSizeFromValue(pageSizeSelect.value);
    state.page = 1;
    await loadCurrentPage({ push: true });
  });

  nextBtn.addEventListener("click", async () => {
    if (!state.hasNext) return;
    state.page += 1;
    await loadCurrentPage({ push: true });
  });
  prevBtn.addEventListener("click", async () => {
    if (!state.hasPrevious) return;
    state.page = Math.max(1, state.page - 1);
    await loadCurrentPage({ push: true });
  });

  for (const tab of viewTabs) {
    tab.addEventListener("click", async () => {
      const nextView = tab.dataset.view || "books";
      if (!VIEWS.has(nextView)) return;
      state.view = nextView;
      state.page = 1;
      if (nextView !== "books") {
        state.q = "";
        state.authorId = "";
        state.authorName = "";
        state.authorBiography = "";
        state.seriesId = "";
        state.seriesName = "";
        state.seriesSummary = "";
        state.contextKey = "";
      }
      await loadCurrentPage({ push: true });
    });
  }

  filterSummaryEl.addEventListener("click", async (e) => {
    const source = e.target;
    if (!(source instanceof Element)) return;
    const proseToggle = source.closest('[data-action="toggle-library-prose"]');
    if (proseToggle && filterSummaryEl.contains(proseToggle)) {
      toggleProseBlock(proseToggle, filterSummaryEl);
      return;
    }

    if (!source.closest('[data-action="clear-library-filter"]')) return;
    state.authorId = "";
    state.authorName = "";
    state.authorBiography = "";
    state.seriesId = "";
    state.seriesName = "";
    state.seriesSummary = "";
    state.contextKey = "";
    state.page = 1;
    await loadCurrentPage({ push: true });
  });

  resultsEl.addEventListener("click", async (e) => {
    const source = e.target;
    if (!(source instanceof Element)) return;

    const authorButton = source.closest('[data-action="browse-author"]');
    if (authorButton) {
      state.view = "books";
      state.q = "";
      state.authorId = authorButton.getAttribute("data-id") || "";
      state.authorName = authorButton.getAttribute("data-name") || "";
      state.authorBiography = "";
      state.seriesId = "";
      state.seriesName = "";
      state.seriesSummary = "";
      state.contextKey = "";
      state.page = 1;
      await loadCurrentPage({ push: true });
      return;
    }

    const seriesButton = source.closest('[data-action="browse-series"]');
    if (seriesButton) {
      state.view = "books";
      state.q = "";
      state.authorId = "";
      state.authorName = "";
      state.authorBiography = "";
      state.seriesId = seriesButton.getAttribute("data-id") || "";
      state.seriesName = seriesButton.getAttribute("data-name") || "";
      state.seriesSummary = "";
      state.contextKey = "";
      state.page = 1;
      await loadCurrentPage({ push: true });
    }
  });

  window.addEventListener("popstate", async () => {
    syncStateFromLocation();
    await loadCurrentPage();
  });
}
