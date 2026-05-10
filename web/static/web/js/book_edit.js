import {
  extractApiErrorMessage,
  fetchJSON,
  fetchJSONWithOptions,
  getCsrfToken,
  summarizeFieldErrors,
} from "./api.js";
import { $, escapeHtml, loadMeAndInitShell, setGlobalErrorFromError, setText, visible } from "./layout.js";

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

function setInlineStatus(el, text, isError) {
  if (!el) return;
  el.textContent = text || "";
  el.classList.toggle("error", !!isError);
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

function schemeOptionsHtml(selected) {
  return IDENT_SCHEMES.map(([v, label]) => {
    const sel = selected && String(selected) === v ? " selected" : "";
    return `<option value="${escapeHtml(v)}"${sel}>${escapeHtml(label)}</option>`;
  }).join("");
}

function initTabs() {
  const buttons = Array.from(document.querySelectorAll(".tab-button[data-tab]"));
  const panels = Array.from(document.querySelectorAll("[data-tab-panel]"));
  if (!buttons.length || !panels.length) return;

  function show(tab) {
    for (const btn of buttons) {
      btn.classList.toggle("is-active", btn.dataset.tab === tab);
    }
    for (const panel of panels) {
      panel.classList.toggle("is-hidden", panel.dataset.tabPanel !== tab);
    }
  }

  for (const btn of buttons) {
    btn.addEventListener("click", () => show(btn.dataset.tab || "metadata"));
  }

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

  let original = null;
  let originalAuthorIds = [];
  let originalSeriesId = null;

  let selectedAuthors = [];
  let allAuthors = [];
  let allSeries = [];

  let identifiers = [];
  let groups = [];
  let allGroups = [];

  function renderHeader(book) {
    const title = book && book.title ? String(book.title) : "Book";
    setText(headerTitleEl, title);

    const authorNames = Array.isArray(book && book.authors) ? book.authors.map((a) => a && a.name).filter(Boolean) : [];
    setText(headerAuthorsEl, authorNames.length ? `Authors: ${authorNames.join(", ")}` : "Authors: (none)");

    const seriesName = book && book.series && book.series.name ? String(book.series.name) : "";
    const seriesIndex = book && book.series_index != null && book.series_index !== "" ? String(book.series_index) : "";
    const seriesLine = seriesName ? `Series: ${seriesName}${seriesIndex ? " · " + seriesIndex : ""}` : "Series: (none)";
    setText(headerSeriesEl, seriesLine);

    const file = book && book.file ? book.file : null;
    if (!file) {
      headerFileEl.innerHTML = '<span class="pill">No file</span>';
    } else {
      const fmt = file.format ? String(file.format).toUpperCase() : "EPUB";
      const size = file.file_size != null && file.file_size !== "" ? `${escapeHtml(file.file_size)} bytes` : "";
      const downloadUrl = file.download_url || "";
      const dl = downloadUrl ? `<a class="pill" href="${escapeHtml(downloadUrl)}">Download ${escapeHtml(fmt)}</a>` : "";
      headerFileEl.innerHTML = `${dl}${size ? ` <span class="muted">${escapeHtml(size)}</span>` : ""}`.trim();
    }
  }

  function renderFileInfo(book) {
    const file = book && book.file ? book.file : null;
    if (!file) {
      fileInfoEl.innerHTML = "<h3 class=\"card__title\">File info</h3><div class=\"muted\">No stored file.</div>";
      return;
    }
    const fmt = file.format ? String(file.format).toUpperCase() : "EPUB";
    const size = file.file_size != null && file.file_size !== "" ? `${escapeHtml(file.file_size)} bytes` : "";
    const checksumShort = file.checksum_short ? String(file.checksum_short) : "";
    const downloadUrl = file.download_url || "";
    const dl = downloadUrl ? `<a class="pill" href="${escapeHtml(downloadUrl)}">Download</a>` : "";
    fileInfoEl.innerHTML = `
      <h3 class="card__title">File info</h3>
      <div class="kv">
        <div class="kv__k">Format</div><div class="kv__v">${escapeHtml(fmt)}</div>
        <div class="kv__k">Size</div><div class="kv__v">${escapeHtml(size || "")}</div>
        <div class="kv__k">Checksum</div><div class="kv__v">${escapeHtml(checksumShort || "")}</div>
        <div class="kv__k">Download</div><div class="kv__v">${dl}</div>
      </div>
    `.trim();
  }

  function renderSelectedAuthors() {
    if (!selectedAuthors.length) {
      authorsSelectedEl.innerHTML = '<div class="muted">No authors.</div>';
      return;
    }
    const rows = selectedAuthors
      .map((a) => {
        const id = a && a.id != null ? String(a.id) : "";
        const name = a && a.name ? String(a.name) : id;
        return `<li>
            ${escapeHtml(name)} <span class="muted"><code>${escapeHtml(id)}</code></span>
            <button class="linklike" type="button" data-remove-author-id="${escapeHtml(id)}" style="margin-left: 8px;">Remove</button>
          </li>`;
      })
      .join("");
    authorsSelectedEl.innerHTML = `<ul>${rows}</ul>`;
  }

  function syncAuthorSelectOptions() {
    const currentIds = new Set(selectedAuthors.map((a) => String(a.id)));
    const options = allAuthors
      .slice()
      .sort((a, b) => String(a.name || "").localeCompare(String(b.name || "")))
      .filter((a) => a && a.id && !currentIds.has(String(a.id)))
      .slice(0, 500)
      .map((a) => `<option value="${escapeHtml(String(a.id))}">${escapeHtml(String(a.name || a.id))}</option>`)
      .join("");
    authorAddSelectEl.innerHTML = options ? options : '<option value="">(No available authors)</option>';
    authorAddBtnEl.disabled = !options;
  }

  function syncSeriesSelectOptions(selectedId) {
    const options = [
      `<option value="">(No series)</option>`,
      ...allSeries
        .slice()
        .sort((a, b) => String(a.name || "").localeCompare(String(b.name || "")))
        .slice(0, 500)
        .map((s) => `<option value="${escapeHtml(String(s.id))}">${escapeHtml(String(s.name || s.id))}</option>`),
    ].join("");
    seriesSelectEl.innerHTML = options;
    seriesSelectEl.value = selectedId || "";
  }

  function renderGroups() {
    if (!groups.length) {
      groupsEl.innerHTML = '<div class="muted">No visible groups.</div>';
      return;
    }
    const rows = groups
      .slice()
      .sort((a, b) => `${a.name || ""}:${a.slug || ""}`.localeCompare(`${b.name || ""}:${b.slug || ""}`))
      .map((g) => {
        const id = g.id ? String(g.id) : "";
        const href = id ? `/groups/${encodeURIComponent(id)}/` : "#";
        const badge = g.is_public_group ? ' <span class="pill pill--owner">Public</span>' : "";
        const removeBtn = g.is_public_group
          ? ""
          : ` <button class="linklike" type="button" data-group-remove-id="${escapeHtml(id)}">Remove</button>`;
        return `<li>
            <a href="${escapeHtml(href)}">${escapeHtml(g.name || "")}</a>
            <span class="muted"><code>${escapeHtml(g.slug || "")}</code></span>${badge}${removeBtn}
          </li>`;
      })
      .join("");
    groupsEl.innerHTML = `<ul>${rows}</ul>`;
  }

  function syncGroupsAddOptions() {
    const currentIds = new Set(groups.map((g) => String(g.id)));
    const options = allGroups
      .slice()
      .sort((a, b) => String(a.name || "").localeCompare(String(b.name || "")))
      .filter((g) => g && g.id && !currentIds.has(String(g.id)))
      .slice(0, 500)
      .map((g) => `<option value="${escapeHtml(String(g.id))}">${escapeHtml(String(g.name || g.slug || g.id))}</option>`)
      .join("");
    groupsAddSelectEl.innerHTML = options ? options : '<option value="">(No available groups)</option>';
    groupsAddBtnEl.disabled = !options;
  }

  function renderIdentifiersTable() {
    const rows = identifiers
      .slice()
      .sort((a, b) => `${a.scheme || ""}:${a.value || ""}`.localeCompare(`${b.scheme || ""}:${b.value || ""}`))
      .map((it) => {
        const id = it.id ? String(it.id) : "";
        const scheme = it.scheme || "other";
        const value = it.value || "";
        const source = it.source || "";
        const primary = !!it.is_primary;
        return `
          <tr data-ident-id="${escapeHtml(id)}">
            <td><select data-ident-field="scheme">${schemeOptionsHtml(scheme)}</select></td>
            <td><input data-ident-field="value" type="text" value="${escapeHtml(value)}" style="width: 100%;" /></td>
            <td><input data-ident-field="source" type="text" value="${escapeHtml(source)}" style="width: 100%;" /></td>
            <td style="text-align: center;"><input data-ident-field="is_primary" type="checkbox" ${primary ? "checked" : ""} /></td>
            <td class="ident-actions">
              <button class="button" type="button" data-ident-action="save">Save</button>
              <button class="button" type="button" data-ident-action="delete">Delete</button>
              <span class="muted" data-ident-status=""></span>
            </td>
          </tr>
        `.trim();
      })
      .join("");

    const addRow = `
      <tr data-ident-add="1">
        <td><select data-ident-add-field="scheme">${schemeOptionsHtml("isbn_13")}</select></td>
        <td><input data-ident-add-field="value" type="text" style="width: 100%;" /></td>
        <td><input data-ident-add-field="source" type="text" value="manual" style="width: 100%;" /></td>
        <td style="text-align: center;"><input data-ident-add-field="is_primary" type="checkbox" /></td>
        <td class="ident-actions">
          <button class="button" type="button" data-ident-action="add">Add</button>
          <span class="muted" data-ident-status=""></span>
        </td>
      </tr>
    `.trim();

    identifiersEl.innerHTML = `
      <div class="ident-tablewrap">
        <table class="ident-table">
          <thead>
            <tr>
              <th>Scheme</th>
              <th>Value</th>
              <th>Source</th>
              <th>Primary</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            ${rows || ""}
            ${addRow}
          </tbody>
        </table>
      </div>
    `.trim();
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

  async function refreshBook() {
    const book = await fetchJSON(`/api/v1/library/books/${encodeURIComponent(String(bookId))}/`);
    original = book;
    identifiers = Array.isArray(book.identifiers) ? book.identifiers : identifiers;
    groups = Array.isArray(book.groups) ? book.groups : groups;
    selectedAuthors = uniqueById(Array.isArray(book.authors) ? book.authors : selectedAuthors);
    originalAuthorIds = selectedAuthors.map((a) => String(a.id)).filter(Boolean);
    originalSeriesId = book.series && book.series.id ? String(book.series.id) : null;

    titleEl.value = book.title || "";
    subtitleEl.value = book.subtitle != null ? String(book.subtitle) : "";
    summaryEl.value = book.summary || "";
    publisherEl.value = book.publisher || "";
    languageEl.value = book.language || "";
    publishedDateEl.value = book.published_date || "";
    isbnEl.value = book.isbn || "";
    subjectsEl.value = subjectsToTextareaValue(book.subjects);
    seriesIndexEl.value = book.series_index != null && book.series_index !== "" ? String(book.series_index) : "";

    renderHeader(book);
    renderFileInfo(book);
    renderSelectedAuthors();
    syncAuthorSelectOptions();
    syncSeriesSelectOptions(originalSeriesId);
    renderGroups();
    syncGroupsAddOptions();
    renderIdentifiersTable();
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

  // Load option lists (paged) for dropdowns.
  setInlineStatus(authorsStatusEl, "Loading…", false);
  setInlineStatus(seriesStatusEl, "Loading…", false);
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

  try {
    allSeries = uniqueById(await fetchAllPages("/api/v1/library/series/"));
    setInlineStatus(seriesStatusEl, `Loaded ${allSeries.length}.`, false);
    syncSeriesSelectOptions(originalSeriesId);
  } catch (e2) {
    console.error("Failed to load series", e2);
    setInlineStatus(seriesStatusEl, "Failed to load.", true);
    setError(`Failed to load series: ${extractApiErrorMessage(e2)}`);
    allSeries = [];
    syncSeriesSelectOptions(originalSeriesId);
  }

  setInlineStatus(groupsStatusEl, "Loading…", false);
  try {
    allGroups = uniqueById(await fetchAllPages("/api/v1/library/groups/"));
    setInlineStatus(groupsStatusEl, "", false);
    syncGroupsAddOptions();
  } catch (e3) {
    console.error("Failed to load groups list", e3);
    setInlineStatus(groupsStatusEl, "Failed to load.", true);
    setError(`Failed to load groups: ${extractApiErrorMessage(e3)}`);
    allGroups = [];
    syncGroupsAddOptions();
  }

  // Identifiers list comes from dedicated endpoint (keeps ids/created_at/updated_at).
  await refreshIdentifiers();

  authorsSelectedEl.addEventListener("click", (ev) => {
    const t = ev.target;
    if (!t || !t.getAttribute) return;
    const id = t.getAttribute("data-remove-author-id");
    if (!id) return;
    selectedAuthors = selectedAuthors.filter((a) => String(a.id) !== String(id));
    renderSelectedAuthors();
    syncAuthorSelectOptions();
    renderHeader({ ...original, authors: selectedAuthors, series: original ? original.series : null, series_index: original ? original.series_index : null, file: original ? original.file : null });
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
    renderHeader({ ...original, authors: selectedAuthors, series: original ? original.series : null, series_index: original ? original.series_index : null, file: original ? original.file : null });
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
      renderHeader({ ...original, authors: selectedAuthors, series: original ? original.series : null, series_index: original ? original.series_index : null, file: original ? original.file : null });
    } catch (e) {
      console.error("Failed to create author", e);
      setInlineStatus(authorsStatusEl, "Create failed.", true);
      setError(`Failed to create author: ${extractApiErrorMessage(e)}`);
    }
  });

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
      const createdId = created && created.id ? String(created.id) : "";
      syncSeriesSelectOptions(createdId);
      renderHeader({ ...original, authors: selectedAuthors, series: created, series_index: seriesIndexEl.value || null, file: original ? original.file : null });
    } catch (e2) {
      console.error("Failed to create series", e2);
      setInlineStatus(seriesStatusEl, "Create failed.", true);
      setError(`Failed to create series: ${extractApiErrorMessage(e2)}`);
    }
  });

  seriesSelectEl.addEventListener("change", () => {
    const sid = seriesSelectEl.value || "";
    const seriesObj = sid ? allSeries.find((s) => String(s.id) === String(sid)) : null;
    renderHeader({ ...original, authors: selectedAuthors, series: seriesObj, series_index: seriesIndexEl.value || null, file: original ? original.file : null });
  });
  seriesIndexEl.addEventListener("input", () => {
    const sid = seriesSelectEl.value || "";
    const seriesObj = sid ? allSeries.find((s) => String(s.id) === String(sid)) : null;
    renderHeader({ ...original, authors: selectedAuthors, series: seriesObj, series_index: seriesIndexEl.value || null, file: original ? original.file : null });
  });

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

      if (!payload.scheme) {
        setError("Scheme is required.");
        return;
      }
      if (!payload.value) {
        setError("Value is required.");
        return;
      }

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

    const patch = {};
    for (const [k, v] of Object.entries(payload)) {
      let oldVal = original ? original[k] : undefined;
      if (k === "authors") oldVal = originalAuthorIds;
      if (k === "series") oldVal = originalSeriesId;
      const oldComparable = oldVal == null ? null : oldVal;
      const newComparable = v == null ? null : v;
      const changed =
        Array.isArray(oldComparable) || Array.isArray(newComparable)
          ? JSON.stringify(oldComparable || []) !== JSON.stringify(newComparable || [])
          : String(oldComparable) !== String(newComparable);
      if (changed) patch[k] = v;
    }

    if (Object.keys(patch).length === 0) {
      setSaved(true);
      setText(saveStatusEl, "No changes.");
      return;
    }

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
        body: JSON.stringify(patch),
      });
      original = updated;
      originalAuthorIds = payload.authors;
      originalSeriesId = payload.series;
      setSaved(true);
      setText(saveStatusEl, "");

      // Refresh header + groups without leaving the page.
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

