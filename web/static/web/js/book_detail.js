import { fetchJSON } from "./api.js";
import { $, loadMeAndInitShell, setGlobalError, setGlobalErrorFromError, visible } from "./layout.js";
import { mountCovers } from "./ui/covers.js";

function initTabs(root) {
  if (!root) return;
  const buttons = Array.from(root.querySelectorAll(".tab-button"));
  const panels = Array.from(root.querySelectorAll("[data-tab-panel]"));
  if (!buttons.length || !panels.length) return;

  function activate(tabName) {
    for (const b of buttons) {
      b.classList.toggle("is-active", b.getAttribute("data-tab") === tabName);
    }
    for (const p of panels) {
      p.classList.toggle("is-hidden", p.getAttribute("data-tab-panel") !== tabName);
    }
  }

  for (const b of buttons) {
    b.addEventListener("click", () => activate(b.getAttribute("data-tab") || ""));
  }

  // Default tab: Shelves
  activate("shelves");
}

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

function renderSubjectsPills(container, subjects) {
  clear(container);
  if (!subjects) return;
  const values = Array.isArray(subjects)
    ? subjects.map((s) => String(s).trim()).filter(Boolean)
    : typeof subjects === "string"
      ? [subjects.trim()].filter(Boolean)
      : [];
  for (const v of values) {
    container.appendChild(el("span", "pill", v));
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
    const source = i && i.source ? String(i.source) : "";
    const isPrimary = !!(i && i.is_primary);

    const code = document.createElement("code");
    code.textContent = scheme;
    li.appendChild(code);
    li.appendChild(document.createTextNode(": " + value));

    if (isPrimary) {
      li.appendChild(document.createTextNode(" "));
      li.appendChild(el("span", "pill", "primary"));
    }
    if (source) {
      li.appendChild(document.createTextNode(" "));
      li.appendChild(el("span", "muted", `(${source})`));
    }

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
  const size = file.file_size != null && file.file_size !== "" ? `${String(file.file_size)} bytes` : "";
  wrap.appendChild(el("div", "", `${format}${size ? ` (${size})` : ""}`));

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
  const ul = document.createElement("ul");
  for (const g of groups) {
    const li = document.createElement("li");
    const gid = g && g.id != null ? String(g.id) : "";
    const name = g && g.name ? String(g.name) : "";
    const isPublic = !!(g && g.is_public_group);

    const a = el("a", "", name);
    a.setAttribute("href", gid ? `/groups/${encodeURIComponent(gid)}/` : "#");
    li.appendChild(a);

    if (isPublic) {
      li.appendChild(document.createTextNode(" "));
      li.appendChild(el("span", "pill pill--owner", "Public"));
    }

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
  const ul = document.createElement("ul");
  for (const s of results) {
    const li = document.createElement("li");
    const sid = s && s.id != null ? String(s.id) : "";
    const name = s && s.name ? String(s.name) : "";
    const a = el("a", "", name || "(Shelf)");
    a.setAttribute("href", sid ? `/shelves/${encodeURIComponent(sid)}/` : "#");
    li.appendChild(a);

    const ownerType = s && s.owner_type ? String(s.owner_type) : "";
    if (ownerType === "user" && s.owner_user && s.owner_user.username) {
      li.appendChild(document.createTextNode(" "));
      li.appendChild(el("span", "muted", `(user: ${String(s.owner_user.username)})`));
    }
    if (ownerType === "group" && s.owner_group && s.owner_group.name) {
      li.appendChild(document.createTextNode(" "));
      li.appendChild(el("span", "muted", `(group: ${String(s.owner_group.name)})`));
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
  const seriesIndex = book && book.series_index != null && book.series_index !== "" ? String(book.series_index) : "";
  const seriesLine = series ? `${series}${seriesIndex ? ` #${seriesIndex}` : ""}` : "";

  const wrap = el("div", "book-meta");

  if (subtitle) wrap.appendChild(el("div", "muted", subtitle));
  if (seriesLine) wrap.appendChild(el("div", "book-meta__line", seriesLine));
  if (authors.length) wrap.appendChild(el("div", "book-meta__line", authors.join(", ")));

  const metaBits = [];
  if (book && book.published_date) metaBits.push(String(book.published_date));
  if (book && book.language) metaBits.push(String(book.language));
  if (metaBits.length) wrap.appendChild(el("div", "muted", metaBits.join(" - ")));

  if (book && book.subjects) {
    const pills = document.createElement("div");
    pills.className = "book-meta__subjects";
    renderSubjectsPills(pills, book.subjects);
    if (pills.textContent && pills.textContent.trim()) wrap.appendChild(pills);
  }

  container.appendChild(wrap);
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
  const groupsSection = $("#book-groups");
  const groupsBody = $("#book-groups-body");
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
    !groupsSection ||
    !groupsBody ||
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
    statusEl.textContent = "Missing book id.";
    statusEl.classList.add("error");
    return;
  }

  const canManage = !!(me && me.capabilities && me.capabilities.can_manage_library);
  visible(editWrapEl, canManage);
  if (canManage) {
    editLinkEl.setAttribute("href", `/library/books/${encodeURIComponent(String(bookId))}/edit/`);
  }

  function setStatus(text, isError) {
    statusEl.textContent = text;
    statusEl.classList.toggle("error", !!isError);
  }

  setStatus("Loading...", false);
  // Initialize tab state immediately so only Shelves is visible on first paint.
  initTabs(detailEl);
  visible(detailEl, false);

  try {
    const book = await fetchJSON(`/api/v1/library/books/${encodeURIComponent(String(bookId))}/`);
    setTitle(book && book.title ? book.title : "Book");

    const titleText = book && book.title ? String(book.title) : "";
    const coverUrl = book && book.cover_url ? String(book.cover_url) : "";
    coverEl.dataset.coverUrl = coverUrl;
    coverEl.dataset.coverTitle = titleText;
    mountCovers(coverEl.parentNode);

    renderBookMeta(metaEl, book);
    renderIdentifiers(idBody, book.identifiers);
    renderFile(filesBody, book.file);
    renderBookGroups(groupsBody, book.groups);

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
      summaryText: book && book.summary ? book.summary : "",
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
    setStatus("", false);
  } catch (e) {
    console.error("Failed to load book detail", { bookId, e });
    if (e && e.status === 404) {
      setStatus("Book not found or not accessible.", true);
    } else {
      setStatus("Error loading book.", true);
      setGlobalErrorFromError(e, "Failed to load book:");
    }
  }
}
