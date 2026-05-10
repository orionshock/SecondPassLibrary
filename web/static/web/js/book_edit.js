import {
  extractApiErrorMessage,
  fetchJSON,
  fetchJSONWithOptions,
  getCsrfToken,
  summarizeFieldErrors,
} from "./api.js";
import { $, loadMeAndInitShell, setGlobalErrorFromError, setText, visible } from "./layout.js";

function clear(node) {
  if (!node) return;
  while (node.firstChild) node.removeChild(node.firstChild);
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function normalizeOptionalString(value) {
  const s = value == null ? "" : String(value);
  const trimmed = s.trim();
  return trimmed ? trimmed : null;
}

function normalizeDateISO(value) {
  const s = normalizeOptionalString(value);
  if (!s) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
  return { error: "Published date must be YYYY-MM-DD." };
}

function normalizeSeriesIndex(value) {
  const s = normalizeOptionalString(value);
  if (!s) return null;
  if (!/^\d+(\.\d)?$/.test(s)) {
    return { error: "Series index must be an integer or one decimal place (e.g. 5 or 5.1)." };
  }
  const n = Number.parseFloat(s);
  if (!Number.isFinite(n)) return { error: "Series index must be a number." };
  if (n < 0) return { error: "Series index must be >= 0." };
  return (Math.round(n * 10) / 10).toFixed(1);
}

function normalizeSubjects(text) {
  const s = text == null ? "" : String(text);
  const raw = s
    .split(/\r?\n|,/g)
    .map((v) => v.trim())
    .filter(Boolean);
  const seen = new Set();
  const out = [];
  for (const item of raw) {
    const key = item.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(item);
  }
  return out;
}

function subjectsToTextareaValue(subjects) {
  if (!subjects) return "";
  if (Array.isArray(subjects)) {
    return subjects.map((s) => String(s).trim()).filter(Boolean).join("\n");
  }
  if (typeof subjects === "string") return subjects.trim();
  return "";
}

async function fetchAllPages(url) {
  const out = [];
  let next = url;
  let safety = 0;
  while (next && safety < 50) {
    const payload = await fetchJSON(next);
    if (payload && Array.isArray(payload.results)) out.push(...payload.results);
    next = payload && payload.next ? payload.next : null;
    safety += 1;
  }
  return out;
}

function setInlineStatus(node, text, isError) {
  if (!node) return;
  node.textContent = text || "";
  node.classList.toggle("error", !!isError);
}

function uniqueById(items) {
  const seen = new Set();
  const out = [];
  for (const item of items || []) {
    const id = item && item.id != null ? String(item.id) : "";
    if (!id || seen.has(id)) continue;
    seen.add(id);
    out.push(item);
  }
  return out;
}

const IDENT_SCHEMES = [
  ["isbn_10", "ISBN-10"],
  ["isbn_13", "ISBN-13"],
  ["asin", "ASIN"],
  ["doi", "DOI"],
  ["oclc", "OCLC"],
  ["lccn", "LCCN"],
  ["openlibrary", "Open Library"],
  ["calibre", "Calibre"],
  ["epub_uid", "EPUB UID"],
  ["publisher", "Publisher"],
  ["uri", "URI/URN"],
  ["uuid", "UUID"],
  ["other", "Other"],
];

function fillSchemeOptions(selectEl, selectedValue) {
  clear(selectEl);
  for (const [v, label] of IDENT_SCHEMES) {
    const opt = document.createElement("option");
    opt.value = v;
    opt.textContent = label;
    if (selectedValue && String(selectedValue) === v) opt.selected = true;
    selectEl.appendChild(opt);
  }
}

function initTabs() {
  const buttons = Array.from(document.querySelectorAll(".tab-button[data-tab]"));
  const panels = Array.from(document.querySelectorAll("[data-tab-panel]"));
  if (!buttons.length || !panels.length) return;

  function show(tab) {
    for (const btn of buttons) btn.classList.toggle("is-active", btn.dataset.tab === tab);
    for (const panel of panels) panel.classList.toggle("is-hidden", panel.dataset.tabPanel !== tab);
  }

  for (const btn of buttons) btn.addEventListener("click", () => show(btn.dataset.tab || "metadata"));
  show("metadata");
}

export async function initBookEdit() {
  const me = await loadMeAndInitShell();
  initTabs();

  const headerEl = $("#book-edit-header");
  const headerTitleEl = $("#book-edit-header-title");
  const headerAuthorsEl = $("#book-edit-header-authors");
  const headerSeriesEl = $("#book-edit-header-series");
  const headerFileEl = $("#book-edit-header-file");

  const rootEl = $("#book-edit");
  const statusEl = $("#book-edit-status");
  const errorEl = $("#book-edit-error");
  const savedEl = $("#book-edit-saved");
  const saveStatusEl = $("#book-edit-save-status");
  const formEl = $("#book-edit-form");
  const saveBtn = $("#book-edit-save");

  const titleEl = $("#book-edit-title");
  const subtitleEl = $("#book-edit-subtitle");
  const summaryEl = $("#book-edit-summary");
  const publisherEl = $("#book-edit-publisher");
  const languageEl = $("#book-edit-language");
  const publishedDateEl = $("#book-edit-published-date");
  const isbnEl = $("#book-edit-isbn");
  const subjectsEl = $("#book-edit-subjects");

  const authorsSelectedEl = $("#book-edit-authors-selected");
  const authorsStatusEl = $("#book-edit-authors-status");
  const authorAddSelectEl = $("#book-edit-author-add-select");
  const authorAddBtnEl = $("#book-edit-author-add-btn");
  const authorNewNameEl = $("#book-edit-author-new-name");
  const authorNewBtnEl = $("#book-edit-author-new-btn");

  const seriesSelectEl = $("#book-edit-series-select");
  const seriesStatusEl = $("#book-edit-series-status");
  const seriesNewNameEl = $("#book-edit-series-new-name");
  const seriesNewBtnEl = $("#book-edit-series-new-btn");
  const seriesIndexEl = $("#book-edit-series-index");

  const groupsStatusEl = $("#book-edit-groups-status");
  const groupsEl = $("#book-edit-groups");
  const groupsAddFormEl = $("#book-edit-groups-add");
  const groupsAddSelectEl = $("#book-edit-groups-add-select");
  const groupsAddBtnEl = $("#book-edit-groups-add-btn");
  const groupsAddStatusEl = $("#book-edit-groups-add-status");

  const identifiersStatusEl = $("#book-edit-identifiers-status");
  const identifiersEl = $("#book-edit-identifiers");
  const fileInfoEl = $("#book-edit-file-info");

  if (
    !headerEl ||
    !headerTitleEl ||
    !headerAuthorsEl ||
    !headerSeriesEl ||
    !headerFileEl ||
    !rootEl ||
    !statusEl ||
    !errorEl ||
    !savedEl ||
    !saveStatusEl ||
    !formEl ||
    !saveBtn ||
    !titleEl ||
    !subtitleEl ||
    !summaryEl ||
    !publisherEl ||
    !languageEl ||
    !publishedDateEl ||
    !isbnEl ||
    !subjectsEl ||
    !authorsSelectedEl ||
    !authorsStatusEl ||
    !authorAddSelectEl ||
    !authorAddBtnEl ||
    !authorNewNameEl ||
    !authorNewBtnEl ||
    !seriesSelectEl ||
    !seriesStatusEl ||
    !seriesNewNameEl ||
    !seriesNewBtnEl ||
    !seriesIndexEl ||
    !groupsStatusEl ||
    !groupsEl ||
    !groupsAddFormEl ||
    !groupsAddSelectEl ||
    !groupsAddBtnEl ||
    !groupsAddStatusEl ||
    !identifiersStatusEl ||
    !identifiersEl ||
    !fileInfoEl
  )
    return;

  function setStatus(text, isError) {
    setText(statusEl, text || "");
    statusEl.classList.toggle("error", !!isError);
  }

  function setError(text) {
    setText(errorEl, text || "");
    visible(errorEl, !!text);
  }

  function setSaved(on) {
    visible(savedEl, !!on);
  }

  function setSaving(on) {
    saveBtn.disabled = !!on;
    if (on) setText(saveStatusEl, "Saving…");
    else setText(saveStatusEl, "");
  }

  const bookId = rootEl.dataset ? rootEl.dataset.bookId : "";
  if (!bookId) {
    setStatus("Missing book id.", true);
    return;
  }

  const canManage = !!(me && me.capabilities && me.capabilities.can_manage_library);
  if (!canManage) {
    setStatus("Not allowed.", true);
    visible(rootEl, false);
    visible(headerEl, false);
    return;
  }

  let book = null;
  let identifiers = [];
  let allAuthors = [];
  let allSeries = [];
  let selectedAuthors = [];
  let allGroups = [];
  let groups = [];

  function renderHeader() {
    const title = book && book.title ? String(book.title) : "Book";
    headerTitleEl.textContent = title;

    const authorNames = Array.isArray(book && book.authors) ? book.authors.map((a) => a && a.name).filter(Boolean) : [];
    headerAuthorsEl.textContent = authorNames.length ? `Authors: ${authorNames.join(", ")}` : "Authors: (none)";

    const seriesName = book && book.series && book.series.name ? String(book.series.name) : "";
    const seriesIdx = book && book.series_index != null && book.series_index !== "" ? String(book.series_index) : "";
    headerSeriesEl.textContent = seriesName ? `Series: ${seriesName}${seriesIdx ? " · " + seriesIdx : ""}` : "Series: (none)";

    clear(headerFileEl);
    const file = book && book.file ? book.file : null;
    if (!file) {
      headerFileEl.appendChild(el("span", "pill", "No file"));
      return;
    }
    const fmt = file.format ? String(file.format).toUpperCase() : "EPUB";
    const downloadUrl = file.download_url ? String(file.download_url) : "";
    if (downloadUrl) {
      const a = el("a", "pill", `Download ${fmt}`);
      a.setAttribute("href", downloadUrl);
      headerFileEl.appendChild(a);
    } else {
      headerFileEl.appendChild(el("span", "pill", fmt));
    }
  }

  function renderFileInfo() {
    clear(fileInfoEl);
    fileInfoEl.appendChild(el("h3", "card__title", "File info"));
    const file = book && book.file ? book.file : null;
    if (!file) {
      fileInfoEl.appendChild(el("div", "muted", "No stored file."));
      return;
    }
    const kv = el("div", "kv");
    function addRow(k, vNodeOrText) {
      kv.appendChild(el("div", "kv__k", k));
      const v = el("div", "kv__v");
      if (vNodeOrText && vNodeOrText.nodeType) v.appendChild(vNodeOrText);
      else v.textContent = vNodeOrText != null ? String(vNodeOrText) : "";
      kv.appendChild(v);
    }
    addRow("Format", file.format ? String(file.format).toUpperCase() : "EPUB");
    addRow("Size", file.file_size != null && file.file_size !== "" ? `${String(file.file_size)} bytes` : "");
    addRow("Checksum", file.checksum_short ? String(file.checksum_short) : "");
    if (file.download_url) {
      const a = el("a", "pill", "Download");
      a.setAttribute("href", String(file.download_url));
      addRow("Download", a);
    } else {
      addRow("Download", "");
    }
    fileInfoEl.appendChild(kv);
  }

  function renderSelectedAuthors() {
    clear(authorsSelectedEl);
    if (!selectedAuthors.length) {
      authorsSelectedEl.appendChild(el("div", "muted", "No authors."));
      return;
    }
    const ul = document.createElement("ul");
    for (const a of selectedAuthors) {
      const id = a && a.id != null ? String(a.id) : "";
      const name = a && a.name ? String(a.name) : id;
      const li = document.createElement("li");
      li.appendChild(document.createTextNode(name + " "));
      const muted = el("span", "muted");
      const code = document.createElement("code");
      code.textContent = id;
      muted.appendChild(code);
      li.appendChild(muted);
      li.appendChild(document.createTextNode(" "));
      const btn = el("button", "linklike", "Remove");
      btn.type = "button";
      btn.style.marginLeft = "8px";
      btn.setAttribute("data-remove-author-id", id);
      li.appendChild(btn);
      ul.appendChild(li);
    }
    authorsSelectedEl.appendChild(ul);
  }

  function syncAuthorSelectOptions() {
    clear(authorAddSelectEl);
    const currentIds = new Set(selectedAuthors.map((a) => String(a.id)));
    const items = allAuthors
      .slice()
      .sort((a, b) => String(a.name || "").localeCompare(String(b.name || "")))
      .filter((a) => a && a.id && !currentIds.has(String(a.id)))
      .slice(0, 500);
    if (!items.length) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "(No available authors)";
      authorAddSelectEl.appendChild(opt);
      authorAddBtnEl.disabled = true;
      return;
    }
    for (const a of items) {
      const opt = document.createElement("option");
      opt.value = String(a.id);
      opt.textContent = String(a.name || a.id);
      authorAddSelectEl.appendChild(opt);
    }
    authorAddBtnEl.disabled = false;
  }

  function syncSeriesSelectOptions(selectedId) {
    clear(seriesSelectEl);
    const none = document.createElement("option");
    none.value = "";
    none.textContent = "(No series)";
    seriesSelectEl.appendChild(none);
    const items = allSeries
      .slice()
      .sort((a, b) => String(a.name || "").localeCompare(String(b.name || "")))
      .slice(0, 500);
    for (const s of items) {
      const opt = document.createElement("option");
      opt.value = String(s.id);
      opt.textContent = String(s.name || s.id);
      seriesSelectEl.appendChild(opt);
    }
    seriesSelectEl.value = selectedId || "";
  }

  function renderGroups() {
    clear(groupsEl);
    if (!groups.length) {
      groupsEl.appendChild(el("div", "muted", "No visible groups."));
      return;
    }
    const ul = document.createElement("ul");
    const items = groups
      .slice()
      .sort((a, b) => `${a.name || ""}:${a.slug || ""}`.localeCompare(`${b.name || ""}:${b.slug || ""}`));
    for (const g of items) {
      const li = document.createElement("li");
      const gid = g && g.id != null ? String(g.id) : "";
      const a = el("a", "", g && g.name ? g.name : "");
      a.setAttribute("href", gid ? `/groups/${encodeURIComponent(gid)}/` : "#");
      li.appendChild(a);
      li.appendChild(document.createTextNode(" "));
      const muted = el("span", "muted");
      const code = document.createElement("code");
      code.textContent = String(g && g.slug ? g.slug : "");
      muted.appendChild(code);
      li.appendChild(muted);
      if (g && g.is_public_group) {
        li.appendChild(document.createTextNode(" "));
        li.appendChild(el("span", "pill pill--owner", "Public"));
      } else if (gid) {
        li.appendChild(document.createTextNode(" "));
        const btn = el("button", "linklike", "Remove");
        btn.type = "button";
        btn.setAttribute("data-group-remove-id", gid);
        li.appendChild(btn);
      }
      ul.appendChild(li);
    }
    groupsEl.appendChild(ul);
  }

  function syncGroupsAddOptions() {
    clear(groupsAddSelectEl);
    const currentIds = new Set(groups.map((g) => String(g.id)));
    const items = allGroups
      .slice()
      .sort((a, b) => String(a.name || "").localeCompare(String(b.name || "")))
      .filter((g) => g && g.id && !currentIds.has(String(g.id)))
      .slice(0, 500);
    if (!items.length) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "(No available groups)";
      groupsAddSelectEl.appendChild(opt);
      groupsAddBtnEl.disabled = true;
      return;
    }
    for (const g of items) {
      const opt = document.createElement("option");
      opt.value = String(g.id);
      opt.textContent = String(g.name || g.slug || g.id);
      groupsAddSelectEl.appendChild(opt);
    }
    groupsAddBtnEl.disabled = false;
  }

  function renderIdentifiersTable() {
    clear(identifiersEl);
    const wrap = el("div", "ident-tablewrap");
    const table = el("table", "ident-table");
    const thead = document.createElement("thead");
    const trh = document.createElement("tr");
    for (const h of ["Scheme", "Value", "Source", "Primary", "Actions"]) trh.appendChild(el("th", "", h));
    thead.appendChild(trh);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    const items = identifiers
      .slice()
      .sort((a, b) => `${a.scheme || ""}:${a.value || ""}`.localeCompare(`${b.scheme || ""}:${b.value || ""}`));

    for (const it of items) {
      const tr = document.createElement("tr");
      const identId = it && it.id != null ? String(it.id) : "";
      tr.setAttribute("data-ident-id", identId);

      const tdScheme = document.createElement("td");
      const schemeSel = document.createElement("select");
      schemeSel.setAttribute("data-ident-field", "scheme");
      fillSchemeOptions(schemeSel, it && it.scheme ? it.scheme : "other");
      tdScheme.appendChild(schemeSel);
      tr.appendChild(tdScheme);

      const tdValue = document.createElement("td");
      const valueInput = document.createElement("input");
      valueInput.type = "text";
      valueInput.style.width = "100%";
      valueInput.setAttribute("data-ident-field", "value");
      valueInput.value = it && it.value != null ? String(it.value) : "";
      tdValue.appendChild(valueInput);
      tr.appendChild(tdValue);

      const tdSource = document.createElement("td");
      const sourceInput = document.createElement("input");
      sourceInput.type = "text";
      sourceInput.style.width = "100%";
      sourceInput.setAttribute("data-ident-field", "source");
      sourceInput.value = it && it.source != null ? String(it.source) : "";
      tdSource.appendChild(sourceInput);
      tr.appendChild(tdSource);

      const tdPrimary = document.createElement("td");
      tdPrimary.style.textAlign = "center";
      const primaryInput = document.createElement("input");
      primaryInput.type = "checkbox";
      primaryInput.setAttribute("data-ident-field", "is_primary");
      primaryInput.checked = !!(it && it.is_primary);
      tdPrimary.appendChild(primaryInput);
      tr.appendChild(tdPrimary);

      const tdActions = el("td", "ident-actions");
      const save = el("button", "button", "Save");
      save.type = "button";
      save.setAttribute("data-ident-action", "save");
      const del = el("button", "button", "Delete");
      del.type = "button";
      del.setAttribute("data-ident-action", "delete");
      const st = el("span", "muted");
      st.setAttribute("data-ident-status", "");
      tdActions.appendChild(save);
      tdActions.appendChild(del);
      tdActions.appendChild(st);
      tr.appendChild(tdActions);

      tbody.appendChild(tr);
    }

    const trAdd = document.createElement("tr");
    trAdd.setAttribute("data-ident-add", "1");

    const tdAScheme = document.createElement("td");
    const sel = document.createElement("select");
    sel.setAttribute("data-ident-add-field", "scheme");
    fillSchemeOptions(sel, "isbn_13");
    tdAScheme.appendChild(sel);
    trAdd.appendChild(tdAScheme);

    const tdAValue = document.createElement("td");
    const inVal = document.createElement("input");
    inVal.type = "text";
    inVal.style.width = "100%";
    inVal.setAttribute("data-ident-add-field", "value");
    tdAValue.appendChild(inVal);
    trAdd.appendChild(tdAValue);

    const tdASource = document.createElement("td");
    const inSource = document.createElement("input");
    inSource.type = "text";
    inSource.style.width = "100%";
    inSource.value = "manual";
    inSource.setAttribute("data-ident-add-field", "source");
    tdASource.appendChild(inSource);
    trAdd.appendChild(tdASource);

    const tdAPrimary = document.createElement("td");
    tdAPrimary.style.textAlign = "center";
    const inPrim = document.createElement("input");
    inPrim.type = "checkbox";
    inPrim.setAttribute("data-ident-add-field", "is_primary");
    tdAPrimary.appendChild(inPrim);
    trAdd.appendChild(tdAPrimary);

    const tdAActions = el("td", "ident-actions");
    const addBtn = el("button", "button", "Add");
    addBtn.type = "button";
    addBtn.setAttribute("data-ident-action", "add");
    const addStatus = el("span", "muted");
    addStatus.setAttribute("data-ident-status", "");
    tdAActions.appendChild(addBtn);
    tdAActions.appendChild(addStatus);
    trAdd.appendChild(tdAActions);

    tbody.appendChild(trAdd);
    table.appendChild(tbody);
    wrap.appendChild(table);
    identifiersEl.appendChild(wrap);
  }

  async function refreshBook() {
    book = await fetchJSON(`/api/v1/library/books/${encodeURIComponent(String(bookId))}/`);

    titleEl.value = book.title || "";
    subtitleEl.value = book.subtitle != null ? String(book.subtitle) : "";
    summaryEl.value = book.summary || "";
    publisherEl.value = book.publisher || "";
    languageEl.value = book.language || "";
    publishedDateEl.value = book.published_date || "";
    isbnEl.value = book.isbn || "";
    subjectsEl.value = subjectsToTextareaValue(book.subjects);
    seriesIndexEl.value = book.series_index != null && book.series_index !== "" ? String(book.series_index) : "";

    selectedAuthors = uniqueById(Array.isArray(book.authors) ? book.authors : []);
    groups = Array.isArray(book.groups) ? book.groups : [];

    renderHeader();
    renderFileInfo();
    renderSelectedAuthors();
    syncAuthorSelectOptions();
    syncSeriesSelectOptions(book.series && book.series.id ? String(book.series.id) : "");
    renderGroups();
    syncGroupsAddOptions();
  }

  async function refreshIdentifiers() {
    setInlineStatus(identifiersStatusEl, "Loading…", false);
    try {
      const list = await fetchJSON(`/api/v1/library/books/${encodeURIComponent(String(bookId))}/identifiers/`);
      identifiers = Array.isArray(list) ? list : [];
      setInlineStatus(identifiersStatusEl, "", false);
      renderIdentifiersTable();
    } catch (e) {
      console.error("Failed to load identifiers", e);
      setInlineStatus(identifiersStatusEl, "Failed to load.", true);
      setError(`Failed to load identifiers: ${extractApiErrorMessage(e)}`);
      identifiers = [];
      renderIdentifiersTable();
    }
  }

  setStatus("Loading…", false);
  setError("");
  setSaved(false);
  visible(rootEl, false);
  visible(headerEl, false);

  try {
    await refreshBook();
    visible(headerEl, true);
    visible(rootEl, true);
    setStatus("", false);
  } catch (e) {
    console.error("Failed to load book for edit", { bookId, e });
    if (e && e.status === 404) setStatus("Book not found or not accessible.", true);
    else {
      setStatus("Error loading book.", true);
      setGlobalErrorFromError(e, "Failed to load book:");
    }
    return;
  }

  // Load option lists.
  setInlineStatus(authorsStatusEl, "Loading…", false);
  try {
    allAuthors = uniqueById(await fetchAllPages("/api/v1/library/authors/"));
    setInlineStatus(authorsStatusEl, `Loaded ${allAuthors.length}.`, false);
    syncAuthorSelectOptions();
  } catch (e) {
    console.error("Failed to load authors", e);
    setInlineStatus(authorsStatusEl, "Failed to load.", true);
    setError(`Failed to load authors: ${extractApiErrorMessage(e)}`);
    allAuthors = [];
    syncAuthorSelectOptions();
  }

  setInlineStatus(seriesStatusEl, "Loading…", false);
  try {
    allSeries = uniqueById(await fetchAllPages("/api/v1/library/series/"));
    setInlineStatus(seriesStatusEl, `Loaded ${allSeries.length}.`, false);
    syncSeriesSelectOptions(book && book.series && book.series.id ? String(book.series.id) : "");
  } catch (e2) {
    console.error("Failed to load series", e2);
    setInlineStatus(seriesStatusEl, "Failed to load.", true);
    setError(`Failed to load series: ${extractApiErrorMessage(e2)}`);
    allSeries = [];
    syncSeriesSelectOptions("");
  }

  setInlineStatus(groupsStatusEl, "Loading…", false);
  try {
    allGroups = uniqueById(await fetchAllPages("/api/v1/library/groups/"));
    setInlineStatus(groupsStatusEl, "", false);
    syncGroupsAddOptions();
  } catch (e3) {
    console.error("Failed to load groups", e3);
    setInlineStatus(groupsStatusEl, "Failed to load.", true);
    setError(`Failed to load groups: ${extractApiErrorMessage(e3)}`);
    allGroups = [];
    syncGroupsAddOptions();
  }

  await refreshIdentifiers();

  // Authors interactions
  authorsSelectedEl.addEventListener("click", (ev) => {
    const t = ev.target;
    if (!t || !t.getAttribute) return;
    const id = t.getAttribute("data-remove-author-id");
    if (!id) return;
    selectedAuthors = selectedAuthors.filter((a) => String(a.id) !== String(id));
    renderSelectedAuthors();
    syncAuthorSelectOptions();
    if (book) book.authors = selectedAuthors;
    renderHeader();
  });

  authorAddBtnEl.addEventListener("click", () => {
    const id = authorAddSelectEl.value || "";
    if (!id) return;
    const found = allAuthors.find((a) => String(a.id) === String(id));
    if (!found) return;
    if (selectedAuthors.some((a) => String(a.id) === String(id))) return;
    selectedAuthors.push(found);
    selectedAuthors = uniqueById(selectedAuthors);
    renderSelectedAuthors();
    syncAuthorSelectOptions();
    if (book) book.authors = selectedAuthors;
    renderHeader();
  });

  authorNewBtnEl.addEventListener("click", async () => {
    setError("");
    const name = (authorNewNameEl.value || "").trim();
    if (!name) {
      setError("Author name is required.");
      return;
    }
    const csrf = getCsrfToken();
    if (!csrf) {
      setError("Missing CSRF token cookie. Reload the page and try again.");
      return;
    }
    setInlineStatus(authorsStatusEl, "Creating…", false);
    try {
      const created = await fetchJSONWithOptions("/api/v1/library/authors/", {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({ name }),
      });
      allAuthors.push(created);
      allAuthors = uniqueById(allAuthors);
      selectedAuthors.push(created);
      selectedAuthors = uniqueById(selectedAuthors);
      authorNewNameEl.value = "";
      setInlineStatus(authorsStatusEl, "Created.", false);
      renderSelectedAuthors();
      syncAuthorSelectOptions();
      if (book) book.authors = selectedAuthors;
      renderHeader();
    } catch (e) {
      console.error("Failed to create author", e);
      setInlineStatus(authorsStatusEl, "Create failed.", true);
      setError(`Failed to create author: ${extractApiErrorMessage(e)}`);
    }
  });

  // Series interactions
  seriesNewBtnEl.addEventListener("click", async () => {
    setError("");
    const name = (seriesNewNameEl.value || "").trim();
    if (!name) {
      setError("Series name is required.");
      return;
    }
    const csrf = getCsrfToken();
    if (!csrf) {
      setError("Missing CSRF token cookie. Reload the page and try again.");
      return;
    }
    setInlineStatus(seriesStatusEl, "Creating…", false);
    try {
      const created = await fetchJSONWithOptions("/api/v1/library/series/", {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({ name }),
      });
      allSeries.push(created);
      allSeries = uniqueById(allSeries);
      seriesNewNameEl.value = "";
      setInlineStatus(seriesStatusEl, "Created.", false);
      syncSeriesSelectOptions(created && created.id ? String(created.id) : "");
      if (book) book.series = created;
      renderHeader();
    } catch (e2) {
      console.error("Failed to create series", e2);
      setInlineStatus(seriesStatusEl, "Create failed.", true);
      setError(`Failed to create series: ${extractApiErrorMessage(e2)}`);
    }
  });

  seriesSelectEl.addEventListener("change", () => {
    const sid = seriesSelectEl.value || "";
    book.series = sid ? allSeries.find((s) => String(s.id) === String(sid)) : null;
    renderHeader();
  });
  seriesIndexEl.addEventListener("input", () => {
    if (book) book.series_index = seriesIndexEl.value || null;
    renderHeader();
  });

  // Groups interactions
  groupsEl.addEventListener("click", async (ev) => {
    const t = ev.target;
    if (!t || !t.getAttribute) return;
    const gid = t.getAttribute("data-group-remove-id");
    if (!gid) return;
    const csrf = getCsrfToken();
    if (!csrf) {
      setError("Missing CSRF token cookie. Reload the page and try again.");
      return;
    }
    setInlineStatus(groupsStatusEl, "Removing…", false);
    try {
      await fetchJSONWithOptions(`/api/v1/library/groups/${encodeURIComponent(String(gid))}/books/${encodeURIComponent(String(bookId))}/`, {
        method: "DELETE",
        headers: { Accept: "application/json", "X-CSRFToken": csrf },
      });
      setInlineStatus(groupsStatusEl, "", false);
      await refreshBook();
    } catch (e) {
      console.error("Remove group assignment failed", e);
      setInlineStatus(groupsStatusEl, "Remove failed.", true);
      setError(`Failed to remove from group: ${extractApiErrorMessage(e)}`);
    }
  });

  groupsAddFormEl.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    setError("");
    setInlineStatus(groupsAddStatusEl, "", false);
    const gid = (groupsAddSelectEl.value || "").trim();
    if (!gid) return;
    const csrf = getCsrfToken();
    if (!csrf) {
      setError("Missing CSRF token cookie. Reload the page and try again.");
      return;
    }
    setInlineStatus(groupsAddStatusEl, "Adding…", false);
    try {
      await fetchJSONWithOptions(`/api/v1/library/groups/${encodeURIComponent(String(gid))}/books/`, {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({ book: String(bookId) }),
      });
      setInlineStatus(groupsAddStatusEl, "Added.", false);
      await refreshBook();
    } catch (e) {
      console.error("Add group assignment failed", e);
      setInlineStatus(groupsAddStatusEl, "Add failed.", true);
      const msg = extractApiErrorMessage(e);
      const body = e && e.body ? e.body : null;
      const fields = summarizeFieldErrors(body);
      setError(fields ? `${msg} (${fields})` : msg);
    }
  });

  // Identifiers interactions (table event delegation)
  identifiersEl.addEventListener("click", async (ev) => {
    const t = ev.target;
    if (!t || !t.getAttribute) return;
    const action = t.getAttribute("data-ident-action");
    if (!action) return;

    const csrf = getCsrfToken();
    if (!csrf) {
      setError("Missing CSRF token cookie. Reload the page and try again.");
      return;
    }

    const row = t.closest ? t.closest("tr") : null;
    if (!row) return;
    const statusSpan = row.querySelector ? row.querySelector("[data-ident-status]") : null;
    const setRowStatus = (text, isError) => setInlineStatus(statusSpan, text, isError);

    if (action === "add") {
      const schemeEl = row.querySelector('[data-ident-add-field="scheme"]');
      const valueEl = row.querySelector('[data-ident-add-field="value"]');
      const sourceEl = row.querySelector('[data-ident-add-field="source"]');
      const primaryEl = row.querySelector('[data-ident-add-field="is_primary"]');
      const payload = {
        scheme: schemeEl && schemeEl.value != null ? String(schemeEl.value).trim() : "",
        value: valueEl && valueEl.value != null ? String(valueEl.value).trim() : "",
        source: sourceEl && sourceEl.value != null ? String(sourceEl.value).trim() : "",
        is_primary: !!(primaryEl && primaryEl.checked),
      };
      if (!payload.scheme) return setError("Scheme is required.");
      if (!payload.value) return setError("Value is required.");
      setRowStatus("Adding…", false);
      try {
        await fetchJSONWithOptions(`/api/v1/library/books/${encodeURIComponent(String(bookId))}/identifiers/`, {
          method: "POST",
          headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": csrf },
          body: JSON.stringify(payload),
        });
        setRowStatus("Added.", false);
        await refreshIdentifiers();
      } catch (e) {
        console.error("Add identifier failed", e);
        setRowStatus("Add failed.", true);
        const msg = extractApiErrorMessage(e);
        const body = e && e.body ? e.body : null;
        const fields = summarizeFieldErrors(body);
        setError(fields ? `${msg} (${fields})` : msg);
      }
      return;
    }

    const identId = row.getAttribute("data-ident-id");
    if (!identId) return;

    if (action === "delete") {
      setRowStatus("Deleting…", false);
      try {
        await fetchJSONWithOptions(
          `/api/v1/library/books/${encodeURIComponent(String(bookId))}/identifiers/${encodeURIComponent(String(identId))}/`,
          { method: "DELETE", headers: { Accept: "application/json", "X-CSRFToken": csrf } }
        );
        setRowStatus("Deleted.", false);
        await refreshIdentifiers();
      } catch (e) {
        console.error("Delete identifier failed", e);
        setRowStatus("Delete failed.", true);
        setError(`Failed to delete identifier: ${extractApiErrorMessage(e)}`);
      }
      return;
    }

    if (action === "save") {
      const schemeEl = row.querySelector('[data-ident-field="scheme"]');
      const valueEl = row.querySelector('[data-ident-field="value"]');
      const sourceEl = row.querySelector('[data-ident-field="source"]');
      const primaryEl = row.querySelector('[data-ident-field="is_primary"]');
      const payload = {
        scheme: schemeEl && schemeEl.value != null ? String(schemeEl.value).trim() : "",
        value: valueEl && valueEl.value != null ? String(valueEl.value).trim() : "",
        source: sourceEl && sourceEl.value != null ? String(sourceEl.value).trim() : "",
        is_primary: !!(primaryEl && primaryEl.checked),
      };
      setRowStatus("Saving…", false);
      try {
        await fetchJSONWithOptions(
          `/api/v1/library/books/${encodeURIComponent(String(bookId))}/identifiers/${encodeURIComponent(String(identId))}/`,
          {
            method: "PATCH",
            headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": csrf },
            body: JSON.stringify(payload),
          }
        );
        setRowStatus("Saved.", false);
        await refreshIdentifiers();
      } catch (e) {
        console.error("Save identifier failed", e);
        setRowStatus("Save failed.", true);
        const msg = extractApiErrorMessage(e);
        const body = e && e.body ? e.body : null;
        const fields = summarizeFieldErrors(body);
        setError(fields ? `${msg} (${fields})` : msg);
      }
    }
  });

  async function saveBook() {
    setError("");
    setSaved(false);

    const title = (titleEl.value || "").trim();
    if (!title) {
      setError("Title is required.");
      return;
    }

    const publishedDate = normalizeDateISO(publishedDateEl.value);
    if (publishedDate && typeof publishedDate === "object" && publishedDate.error) {
      setError(publishedDate.error);
      return;
    }

    const seriesIndex = normalizeSeriesIndex(seriesIndexEl.value);
    if (seriesIndex && typeof seriesIndex === "object" && seriesIndex.error) {
      setError(seriesIndex.error);
      return;
    }

    const payload = {
      title,
      subtitle: (subtitleEl.value || "").trim(),
      summary: normalizeOptionalString(summaryEl.value),
      publisher: normalizeOptionalString(publisherEl.value),
      language: normalizeOptionalString(languageEl.value),
      published_date: publishedDate,
      isbn: normalizeOptionalString(isbnEl.value),
      subjects: normalizeSubjects(subjectsEl.value),
      authors: selectedAuthors.map((a) => String(a.id)).filter(Boolean),
      series: seriesSelectEl.value ? String(seriesSelectEl.value) : null,
      series_index: seriesIndex,
    };

    const csrf = getCsrfToken();
    if (!csrf) {
      setError("Missing CSRF token cookie. Reload the page and try again.");
      return;
    }

    setSaving(true);
    try {
      const updated = await fetchJSONWithOptions(`/api/v1/library/books/${encodeURIComponent(String(bookId))}/`, {
        method: "PATCH",
        headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify(payload),
      });
      book = updated;
      setSaved(true);
      setText(saveStatusEl, "");
      await refreshBook();
      await refreshIdentifiers();
    } catch (e) {
      console.error("Failed to save book", { bookId, e });
      const msg = extractApiErrorMessage(e);
      const body = e && e.body ? e.body : null;
      const fields = summarizeFieldErrors(body);
      setError(fields ? `${msg} (${fields})` : msg);
    } finally {
      setSaving(false);
    }
  }

  formEl.addEventListener("submit", (ev) => {
    ev.preventDefault();
    saveBook().catch((e) => {
      console.error("saveBook failed", e);
      setError(extractApiErrorMessage(e));
    });
  });
}

