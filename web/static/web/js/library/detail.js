import { fetchJSON } from "../api.js";
import { canManageLibrary } from "../auth.js";
import {
  $,
  advancedLibraryGroupsEnabled,
  loadMeAndInitShell,
  setGlobalError,
  setGlobalErrorFromError,
  visible,
} from "../layout.js";
import { setBreadcrumbs } from "../ui/breadcrumbs.js";
import { renderShelfMetadata } from "../shelves/shared.js";
import { mountCovers } from "../ui/covers.js";
import { renderGroupBadge } from "../ui/groups.js";
import { setStatus } from "../ui/status.js";
import { initTabs } from "../ui/tabs.js";
import { bookDetailContextFromSearch, libraryContextHref } from "./navigation.js";

function setupSummary({ summaryWrapEl, summaryEl, toggleEl, summaryText }) {
  if (!summaryWrapEl || !summaryEl || !toggleEl) return;
  const text = String(summaryText || "").trim();
  visible(summaryWrapEl, !!text);
  if (!text) return;

  summaryEl.textContent = text;
  summaryEl.classList.add("book-hero__summary--clamped");
  toggleEl.textContent = "Show more";
  visible(toggleEl, false);

  // Wait for layout so we can detect truncation.
  window.requestAnimationFrame(() => {
    const isClamped = summaryEl.scrollHeight > summaryEl.clientHeight + 1;
    visible(toggleEl, isClamped);
  });

  toggleEl.addEventListener("click", () => {
    const clamped = summaryEl.classList.toggle("book-hero__summary--clamped");
    toggleEl.textContent = clamped ? "Show more" : "Show less";
  });
}

function clear(el) {
  if (!el) return;
  while (el.firstChild) el.removeChild(el.firstChild);
}

function formatBytes(byteCount) {
  const n = typeof byteCount === "number" ? byteCount : Number(byteCount);
  if (!Number.isFinite(n) || n < 0) return "";
  if (n < 1024) return `${n} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = n / 1024;
  let unitIdx = 0;
  while (value >= 1024 && unitIdx < units.length - 1) {
    value /= 1024;
    unitIdx += 1;
  }
  const rounded = value >= 10 ? Math.round(value) : Math.round(value * 10) / 10;
  return `${rounded} ${units[unitIdx]}`;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function setTitle(text) {
  const titleEl = $("#book-title");
  if (!titleEl) return;
  titleEl.textContent = text;
}

function bookDisplayTitle(book) {
  return book && book.title ? String(book.title) : "Untitled book";
}

function syncBookBreadcrumbs({ title, context = null }) {
  if (context && context.kind === "author") {
    setBreadcrumbs([
      { label: "Library", href: "/library/" },
      { label: "Authors", href: "/library/?view=authors" },
      { label: context.name || "Author", href: libraryContextHref(context) },
      { label: title || "Book", current: true },
    ]);
    return;
  }
  if (context && context.kind === "series") {
    setBreadcrumbs([
      { label: "Library", href: "/library/" },
      { label: "Series", href: "/library/?view=series" },
      { label: context.name || "Series", href: libraryContextHref(context) },
      { label: title || "Book", current: true },
    ]);
    return;
  }

  setBreadcrumbs([
    { label: "Library", href: "/library/" },
    { label: "Books", href: "/library/?view=books" },
    { label: title || "Book", current: true },
  ]);
}

async function loadBreadcrumbContext(context) {
  if (!context || !context.id || (context.kind !== "author" && context.kind !== "series")) return null;
  try {
    const endpoint = context.kind === "author" ? "authors" : "series";
    const payload = await fetchJSON(`/api/v1/library/${endpoint}/${encodeURIComponent(context.id)}/`);
    return {
      ...context,
      name: payload && payload.name ? String(payload.name) : context.name,
    };
  } catch (e) {
    console.warn("Failed to load book breadcrumb context", { context, e });
    return context;
  }
}

function renderCatalogTagPills(container, tags) {
  clear(container);
  const values = Array.isArray(tags) ? tags : [];
  for (const tag of values) {
    const name = tag && tag.name ? String(tag.name) : "";
    if (!name) continue;
    container.appendChild(el("span", "pill", name));
    container.appendChild(document.createTextNode(" "));
  }
}

function renderIdentifiers(container, identifiers) {
  clear(container);
  if (!Array.isArray(identifiers) || identifiers.length === 0) {
    container.appendChild(el("div", "muted", "No identifiers."));
    return;
  }
  const ul = document.createElement("ul");
  for (const i of identifiers) {
    const li = document.createElement("li");
    const scheme = i && i.scheme ? String(i.scheme) : "";
    const value = i && i.value ? String(i.value) : "";

    const code = document.createElement("code");
    code.textContent = scheme;
    li.appendChild(code);
    li.appendChild(document.createTextNode(": " + value));

    ul.appendChild(li);
  }
  container.appendChild(ul);
}

function renderFile(container, file) {
  clear(container);
  if (!file) {
    container.appendChild(el("div", "muted", "No file."));
    return;
  }

  const wrap = document.createElement("div");
  const format = file.format ? String(file.format).toUpperCase() : "EPUB";
  const size = formatBytes(file.file_size);
  wrap.appendChild(el("div", "", `${format}${size ? ` (${size})` : ""}`));
  if (file.checksum) wrap.appendChild(el("div", "muted", `Checksum: ${file.checksum}`));
  if (file.source_filename) wrap.appendChild(el("div", "muted", `Source filename: ${file.source_filename}`));

  const downloadUrl = file.download_url ? String(file.download_url) : "";
  if (downloadUrl) {
    wrap.appendChild(document.createTextNode(" "));
    const a = el("a", "pill", "Download file");
    a.setAttribute("href", downloadUrl);
    wrap.appendChild(a);
  }

  container.appendChild(wrap);
}

function renderBookGroups(container, groups) {
  clear(container);
  if (!Array.isArray(groups) || groups.length === 0) {
    container.appendChild(el("div", "muted", "No visible groups."));
    return;
  }
  const ul = el("ul", "compact-list");
  for (const g of groups) {
    const li = el("li", "compact-list__item");
    const gid = g && g.id != null ? String(g.id) : "";
    const a = el("a", "");
    a.setAttribute("href", gid ? `/groups/${encodeURIComponent(gid)}/` : "#");
    a.appendChild(renderGroupBadge(g, { compact: true }));
    li.appendChild(a);

    ul.appendChild(li);
  }
  container.appendChild(ul);
}

function renderBookShelves(container, shelves) {
  clear(container);
  const results = Array.isArray(shelves && shelves.results) ? shelves.results : Array.isArray(shelves) ? shelves : [];
  if (!Array.isArray(results) || results.length === 0) {
    container.appendChild(el("div", "muted", "No visible shelves."));
    return;
  }
  const ul = el("ul", "compact-list");
  for (const s of results) {
    const li = el("li", "compact-list__item");
    const sid = s && s.id != null ? String(s.id) : "";
    const name = s && s.name ? String(s.name) : "";
    const a = el("a", "", name || "(Shelf)");
    a.setAttribute("href", sid ? `/shelves/${encodeURIComponent(sid)}/` : "#");
    li.appendChild(a);

    const metadata = renderShelfMetadata(s);
    if (metadata.childNodes.length) {
      const meta = el("span", "muted");
      meta.appendChild(metadata);
      li.appendChild(meta);
    }

    ul.appendChild(li);
  }
  container.appendChild(ul);
}

function renderBookMeta(container, book) {
  clear(container);
  const subtitle = book && book.subtitle ? String(book.subtitle) : "";
  const authors = Array.isArray(book && book.authors) ? book.authors.map((a) => a && a.name).filter(Boolean) : [];
  const series = book && book.series && book.series.name ? String(book.series.name) : "";
  const seriesIndex = book && book.series && book.series.series_index != null ? String(book.series.series_index) : "";
  const seriesLine = series ? `${series}${seriesIndex ? ` #${seriesIndex}` : ""}` : "";

  const wrap = el("div", "book-meta");

  if (subtitle) wrap.appendChild(el("div", "muted", subtitle));
  if (seriesLine) wrap.appendChild(el("div", "book-meta__line", seriesLine));
  if (authors.length) wrap.appendChild(el("div", "book-meta__line", authors.join(", ")));

  const metaBits = [];
  const publishedDate = formatPublishedDate(book);
  if (publishedDate) metaBits.push(publishedDate);
  if (book && book.publisher) metaBits.push(String(book.publisher));
  if (book && book.language) metaBits.push(String(book.language));
  if (metaBits.length) wrap.appendChild(el("div", "muted", metaBits.join(" - ")));

  if (book && Array.isArray(book.catalog_tags) && book.catalog_tags.length) {
    const pills = document.createElement("div");
    pills.className = "book-meta__tags";
    renderCatalogTagPills(pills, book.catalog_tags);
    if (pills.textContent && pills.textContent.trim()) wrap.appendChild(pills);
  }

  container.appendChild(wrap);
}

function formatPublishedDate(book) {
  if (!book || !book.published_year) return "";
  const year = String(book.published_year).padStart(4, "0");
  const month = book.published_month ? String(book.published_month).padStart(2, "0") : "";
  const day = book.published_day ? String(book.published_day).padStart(2, "0") : "";
  if (book.published_date_precision === "day" && month && day) return `${year}-${month}-${day}`;
  if (book.published_date_precision === "month" && month) return `${year}-${month}`;
  return year;
}

function renderMetadataDetails(container, book) {
  clear(container);
  const rows = [
    ["Description", book && book.description],
    ["Publisher", book && book.publisher],
    ["Language", book && book.language],
    ["Published date", formatPublishedDate(book)],
  ];
  const grid = el("div", "kv");
  for (const [label, value] of rows) {
    grid.appendChild(el("div", "kv__k", label));
    grid.appendChild(el("div", "kv__v", value || "—"));
  }
  container.appendChild(grid);
}

export async function initBookDetail() {
  const me = await loadMeAndInitShell();
  setGlobalError("");

  const statusEl = $("#book-status");
  const detailEl = $("#book-detail");
  const metaEl = $("#book-meta");
  const coverEl = $("#book-cover");
  const editWrapEl = $("#book-edit-link-wrap");
  const editLinkEl = $("#book-edit-link");
  const idBody = $("#book-identifiers-body");
  const filesBody = $("#book-files-body");
  const metadataBody = $("#book-metadata-body");
  const catalogTagsBody = $("#book-catalog-tags-body");
  const groupsSection = $("#book-groups");
  const groupsBody = $("#book-groups-body");
  const groupsFeatureEnabled =
    advancedLibraryGroupsEnabled() && !!groupsSection && !!groupsBody;
  const shelvesSection = $("#book-shelves");
  const shelvesBody = $("#book-shelves-body");
  const downloadLink = $("#book-download-link");
  const summaryWrapEl = $("#book-summary-wrap");
  const summaryEl = $("#book-summary");
  const summaryToggle = $("#book-summary-toggle");

  if (
    !statusEl ||
    !detailEl ||
    !metaEl ||
    !coverEl ||
    !editWrapEl ||
    !editLinkEl ||
    !idBody ||
    !filesBody ||
    !metadataBody ||
    !catalogTagsBody ||
    !shelvesSection ||
    !shelvesBody ||
    !downloadLink ||
    !summaryWrapEl ||
    !summaryEl ||
    !summaryToggle
  )
    return;

  const bookId = detailEl.dataset ? detailEl.dataset.bookId : "";
  if (!bookId) {
    setStatus(statusEl, "Missing book id.", true);
    return;
  }
  let breadcrumbContext = bookDetailContextFromSearch(window.location.search);
  syncBookBreadcrumbs({ title: "Book", context: breadcrumbContext });

  const canManage = canManageLibrary(me);
  visible(editWrapEl, canManage);
  if (canManage) {
    editLinkEl.setAttribute("href", `/library/books/${encodeURIComponent(String(bookId))}/edit/`);
  }

  setStatus(statusEl, "Loading...", false);
  // Initialize tab state immediately so only Shelves is visible on first paint.
  initTabs(detailEl);
  visible(detailEl, false);

  try {
    const [book, loadedContext] = await Promise.all([
      fetchJSON(`/api/v1/library/books/${encodeURIComponent(String(bookId))}/`),
      loadBreadcrumbContext(breadcrumbContext),
    ]);
    breadcrumbContext = loadedContext;
    const displayTitle = bookDisplayTitle(book);
    setTitle(displayTitle);
    syncBookBreadcrumbs({ title: displayTitle, context: breadcrumbContext });

    const titleText = book && book.title ? String(book.title) : "";
    const coverUrl = book && book.cover_url ? String(book.cover_url) : "";
    coverEl.dataset.coverUrl = coverUrl;
    coverEl.dataset.coverTitle = titleText;
    mountCovers(coverEl.parentNode);

    renderBookMeta(metaEl, book);
    renderIdentifiers(idBody, book.identifiers);
    renderFile(filesBody, book.file);
    renderMetadataDetails(metadataBody, book);
    renderCatalogTagPills(catalogTagsBody, book.catalog_tags);
    if (groupsFeatureEnabled) renderBookGroups(groupsBody, book.groups);

    // Primary action: download
    const dlUrl = book && book.file && book.file.download_url ? String(book.file.download_url) : "";
    const dlFmt = book && book.file && book.file.format ? String(book.file.format).toUpperCase() : "";
    if (dlUrl) {
      downloadLink.setAttribute("href", dlUrl);
      downloadLink.textContent = `Download ${dlFmt || "file"}`;
      visible(downloadLink, true);
    } else {
      visible(downloadLink, false);
    }

    setupSummary({
      summaryWrapEl,
      summaryEl,
      toggleEl: summaryToggle,
      summaryText: book && book.description ? book.description : "",
    });

    // Default tab content should show something immediately.
    shelvesBody.textContent = "Loading...";

    try {
      const shelves = await fetchJSON(`/api/v1/shelves/?book=${encodeURIComponent(String(bookId))}`);
      renderBookShelves(shelvesBody, shelves);
    } catch (e2) {
      console.error("Failed to load shelves for book", { bookId, e2 });
      // Non-fatal: show an empty/unknown state and keep the page usable.
      renderBookShelves(shelvesBody, []);
    }

    visible(detailEl, true);
    setStatus(statusEl, "", false);
  } catch (e) {
    console.error("Failed to load book detail", { bookId, e });
    if (e && e.status === 404) {
      setStatus(statusEl, "Book not found or not accessible.", true);
    } else {
      setStatus(statusEl, "Error loading book.", true);
      setGlobalErrorFromError(e, "Failed to load book:");
    }
  }
}
