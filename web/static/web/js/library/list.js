import { fetchJSON } from "../api.js";
import { $, escapeHtml, loadMeAndInitShell, setGlobalErrorFromError } from "../layout.js";
import { mountCovers } from "../ui/covers.js";
import { setStatus } from "../ui/status.js";

function bookFileHtml(file) {
  if (!file || !file.download_url) return "";
  const label = "Download";
  return `<div class="book__files"><a class="pill" href="${escapeHtml(
    file.download_url
  )}">${escapeHtml(label)}</a></div>`;
}

function renderBooks(payload) {
  const results = Array.isArray(payload && payload.results) ? payload.results : [];
  if (results.length === 0) return "";

  return results
    .map((b) => {
      const title = b.title || "(Untitled)";
      const bookHref = b.id ? `/library/books/${encodeURIComponent(String(b.id))}/` : null;
      const subtitle = b.subtitle ? ` <span class="muted">- ${escapeHtml(b.subtitle)}</span>` : "";
      const authors = Array.isArray(b.authors) ? b.authors.map((a) => a.name).filter(Boolean) : [];
      const series = b.series && b.series.name ? b.series.name : "";
      const seriesIndex = b.series_index != null && b.series_index !== "" ? String(b.series_index) : "";
      const seriesLine = series ? `${series}${seriesIndex ? ` ${seriesIndex}` : ""}` : "";
      const language = b.language || "";
      const coverUrl = b.cover_url ? String(b.cover_url) : "";

      const metaLines = [];
      if (authors.length) metaLines.push(`<div>${escapeHtml(authors.join(", "))}</div>`);
      if (seriesLine) metaLines.push(`<div>${escapeHtml(seriesLine)}</div>`);
      if (language) metaLines.push(`<div>Language: ${escapeHtml(language)}</div>`);

      return `
          <article class="book book--with-cover">
            <div class="book__cover" data-cover-url="${escapeHtml(coverUrl)}" data-cover-title="${escapeHtml(title)}"></div>
            <div>
              <h3 class="book__title">${
                bookHref
                  ? `<a href="${escapeHtml(bookHref)}">${escapeHtml(title)}</a>${subtitle}`
                  : `${escapeHtml(title)}${subtitle}`
              }</h3>
              <div class="book__meta">${metaLines.join("") || '<div class="muted">No metadata.</div>'}</div>
              ${bookFileHtml(b.file)}
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
