import { fetchJSON } from "./api.js";
import { $, loadMeAndInitShell, setGlobalError, setGlobalErrorFromError, visible } from "./layout.js";

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
  wrap.appendChild(el("span", "pill", format));

  const size = file.file_size != null && file.file_size !== "" ? `${String(file.file_size)} bytes` : "";
  wrap.appendChild(document.createTextNode(" "));
  wrap.appendChild(el("span", "muted", size));

  const downloadUrl = file.download_url ? String(file.download_url) : "";
  if (downloadUrl) {
    wrap.appendChild(document.createTextNode(" "));
    const a = el("a", "pill", "Download");
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
    const slug = g && g.slug ? String(g.slug) : "";
    const isPublic = !!(g && g.is_public_group);

    const a = el("a", "", name);
    a.setAttribute("href", gid ? `/groups/${encodeURIComponent(gid)}/` : "#");
    li.appendChild(a);
    li.appendChild(document.createTextNode(" "));

    const muted = el("span", "muted");
    const code = document.createElement("code");
    code.textContent = slug;
    muted.appendChild(code);
    li.appendChild(muted);

    if (isPublic) {
      li.appendChild(document.createTextNode(" "));
      li.appendChild(el("span", "pill pill--owner", "Public"));
    }

    ul.appendChild(li);
  }
  container.appendChild(ul);
}

function renderBookMeta(container, book) {
  clear(container);
  const kv = el("div", "kv");

  function addRow(key, valueNodeOrText) {
    kv.appendChild(el("div", "kv__k", key));
    const v = el("div", "kv__v");
    if (valueNodeOrText && valueNodeOrText.nodeType) v.appendChild(valueNodeOrText);
    else v.textContent = valueNodeOrText != null ? String(valueNodeOrText) : "";
    kv.appendChild(v);
  }

  const title = book && book.title ? String(book.title) : "Book";
  const subtitle = book && book.subtitle ? String(book.subtitle) : "";
  const authors = Array.isArray(book && book.authors) ? book.authors.map((a) => a && a.name).filter(Boolean) : [];
  const series = book && book.series && book.series.name ? String(book.series.name) : "";
  const seriesIndex = book && book.series_index != null && book.series_index !== "" ? String(book.series_index) : "";
  const seriesLine = series ? `${series}${seriesIndex ? " · " + seriesIndex : ""}` : "";

  addRow("Title", title);
  if (subtitle) addRow("Subtitle", subtitle);
  addRow("Authors", authors.join(", ") || "");
  if (seriesLine) addRow("Series", seriesLine);
  if (book && book.summary) addRow("Summary", book.summary);
  if (book && book.publisher) addRow("Publisher", book.publisher);
  if (book && book.language) addRow("Language", book.language);
  if (book && book.published_date) addRow("Published", book.published_date);
  if (book && book.isbn) addRow("ISBN", book.isbn);
  if (book && book.subjects) {
    const pills = document.createElement("div");
    renderSubjectsPills(pills, book.subjects);
    if (pills.textContent && pills.textContent.trim()) addRow("Subjects", pills);
  }

  container.appendChild(kv);
}

export async function initBookDetail() {
  const me = await loadMeAndInitShell();
  setGlobalError("");

  const statusEl = $("#book-status");
  const detailEl = $("#book-detail");
  const metaEl = $("#book-meta");
  const editWrapEl = $("#book-edit-link-wrap");
  const editLinkEl = $("#book-edit-link");
  const idSection = $("#book-identifiers");
  const idBody = $("#book-identifiers-body");
  const filesSection = $("#book-files");
  const filesBody = $("#book-files-body");
  const groupsSection = $("#book-groups");
  const groupsBody = $("#book-groups-body");

  if (
    !statusEl ||
    !detailEl ||
    !metaEl ||
    !editWrapEl ||
    !editLinkEl ||
    !idSection ||
    !idBody ||
    !filesSection ||
    !filesBody ||
    !groupsSection ||
    !groupsBody
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

  setStatus("Loading…", false);
  visible(detailEl, false);
  visible(idSection, false);
  visible(filesSection, false);
  visible(groupsSection, false);

  try {
    const book = await fetchJSON(`/api/v1/library/books/${encodeURIComponent(String(bookId))}/`);
    setTitle(book && book.title ? book.title : "Book");

    renderBookMeta(metaEl, book);
    renderIdentifiers(idBody, book.identifiers);
    renderFile(filesBody, book.file);
    renderBookGroups(groupsBody, book.groups);

    visible(detailEl, true);
    visible(idSection, true);
    visible(filesSection, true);
    visible(groupsSection, true);
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

