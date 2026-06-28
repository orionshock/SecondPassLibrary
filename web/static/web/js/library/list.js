import { fetchJSON } from "../api.js";
import { $, escapeHtml, loadMeAndInitShell, setGlobalErrorFromError } from "../layout.js";
import { mountCovers } from "../ui/covers.js";
import { renderGroupBadge } from "../ui/groups.js";
import { setStatus } from "../ui/status.js";

const DEFAULT_PAGE_SIZE = 20;
const PAGE_SIZE_OPTIONS = [20, 30, 40, 50];

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
  const rangeEl = $("#library-range");
  const resultsEl = $("#library-results");
  const nextBtn = $("#next");
  const prevBtn = $("#prev");
  const form = $("#library-search");
  const qInput = $("#q");
  const pageSizeSelect = $("#library-page-size");

  if (!statusEl || !rangeEl || !resultsEl || !nextBtn || !prevBtn || !form || !qInput || !pageSizeSelect) return;

  const state = {
    q: "",
    page: 1,
    pageSize: DEFAULT_PAGE_SIZE,
    count: 0,
    resultLength: 0,
    hasNext: false,
    hasPrevious: false,
  };

  function syncControls() {
    qInput.value = state.q;
    pageSizeSelect.value = String(state.pageSize);
    rangeEl.textContent = rangeText(state);
    prevBtn.disabled = !state.hasPrevious;
    nextBtn.disabled = !state.hasNext;
  }

  function apiUrlForState() {
    return urlWithParams("/api/v1/library/books/", {
      q: state.q,
      page: state.page,
      page_size: state.pageSize,
    });
  }

  function locationParamsForState() {
    const params = {
      page: state.page,
      page_size: state.pageSize,
    };
    if (state.q) params.q = state.q;
    return params;
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
      const payload = await fetchJSON(url);
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
        setStatus(statusEl, "Empty library.", false);
        syncControls();
        if (push || replace) pushLocation(locationParamsForState(), { replace });
        return;
      }

      setStatus(statusEl, "", false);
      resultsEl.innerHTML = renderBooks(payload);
      mountCovers(resultsEl);
      syncControls();
      if (push || replace) pushLocation(locationParamsForState(), { replace });
    } catch (e) {
      console.error("Failed to load books", { url: apiUrlForState(), e });
      setStatus(statusEl, "Error loading data.", true);
      setGlobalErrorFromError(e, "Failed to load library:");
      state.hasNext = false;
      state.hasPrevious = false;
      syncControls();
    }
  }

  function syncStateFromLocation() {
    const params = new URLSearchParams(window.location.search);
    state.q = (params.get("q") || "").trim();
    state.page = parsePositiveInt(params.get("page"), 1);
    state.pageSize = pageSizeFromValue(params.get("page_size"));
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
    state.q = (qInput.value || "").trim();
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

  window.addEventListener("popstate", async () => {
    syncStateFromLocation();
    await loadCurrentPage();
  });
}
