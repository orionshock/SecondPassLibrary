import { fetchJSON } from "../api.js";
import { $, escapeHtml, loadMeAndInitShell, setGlobalErrorFromError } from "../layout.js";
import { mountCovers } from "../ui/covers.js";
import { renderGroupBadge } from "../ui/groups.js";
import { setStatus } from "../ui/status.js";

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
  const resultsEl = $("#library-results");
  const nextBtn = $("#next");
  const prevBtn = $("#prev");
  const form = $("#library-search");
  const qInput = $("#q");

  if (!statusEl || !resultsEl || !nextBtn || !prevBtn || !form || !qInput) return;

  let nextUrl = null;
  let prevUrl = null;

  async function load(url) {
    setStatus(statusEl, "Loading...", false);
    resultsEl.innerHTML = "";
    nextBtn.disabled = true;
    prevBtn.disabled = true;

    try {
      const payload = await fetchJSON(url);
      const hasAny =
        payload && payload.count
          ? payload.count > 0
          : Array.isArray(payload.results) && payload.results.length > 0;

      if (!hasAny) {
        setStatus(statusEl, "Empty library.", false);
        nextUrl = null;
        prevUrl = null;
        return;
      }

      setStatus(statusEl, "", false);
      resultsEl.innerHTML = renderBooks(payload);
      mountCovers(resultsEl);

      nextUrl = payload.next || null;
      prevUrl = payload.previous || null;
      nextBtn.disabled = !nextUrl;
      prevBtn.disabled = !prevUrl;
    } catch (e) {
      console.error("Failed to load books", { url, e });
      setStatus(statusEl, "Error loading data.", true);
      setGlobalErrorFromError(e, "Failed to load library:");
      nextUrl = null;
      prevUrl = null;
    }
  }

  function syncQueryFromLocation() {
    const params = new URLSearchParams(window.location.search);
    qInput.value = params.get("q") || "";
  }

  function pushLocation(params) {
    const url = new URL(window.location.href);
    url.search = new URLSearchParams(params).toString();
    window.history.pushState({}, "", url.toString());
  }

  syncQueryFromLocation();
  const initialQ = new URLSearchParams(window.location.search).get("q") || "";
  await load(urlWithParams("/api/v1/library/books/", { q: initialQ }));

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const q = (qInput.value || "").trim();
    pushLocation(q ? { q } : {});
    await load(urlWithParams("/api/v1/library/books/", { q }));
  });

  nextBtn.addEventListener("click", async () => {
    if (nextUrl) await load(nextUrl);
  });
  prevBtn.addEventListener("click", async () => {
    if (prevUrl) await load(prevUrl);
  });

  window.addEventListener("popstate", async () => {
    syncQueryFromLocation();
    const q = (qInput.value || "").trim();
    await load(urlWithParams("/api/v1/library/books/", { q }));
  });
}
