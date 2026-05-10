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

  // Allow integers (5) or one-decimal values (5.1). Reject 5.12, -1, non-numeric.
  if (!/^\d+(\.\d)?$/.test(s)) {
    return { error: "Series index must be an integer or one decimal place (e.g. 5 or 5.1)." };
  }
  const n = Number.parseFloat(s);
  if (!Number.isFinite(n)) return { error: "Series index must be a number." };
  if (n < 0) return { error: "Series index must be >= 0." };

  // Normalize to 1 decimal so comparisons match API output (DecimalField emits strings).
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

export async function initBookEdit() {
  const me = await loadMeAndInitShell();

  const rootEl = $("#book-edit");
  const statusEl = $("#book-edit-status");
  const errorEl = $("#book-edit-error");
  const savedEl = $("#book-edit-saved");
  const saveStatusEl = $("#book-edit-save-status");
  const formEl = $("#book-edit-form");
  const saveBtn = $("#book-edit-save");

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

  const titleEl = $("#book-edit-title");
  const subtitleEl = $("#book-edit-subtitle");
  const summaryEl = $("#book-edit-summary");
  const publisherEl = $("#book-edit-publisher");
  const languageEl = $("#book-edit-language");
  const publishedDateEl = $("#book-edit-published-date");
  const isbnEl = $("#book-edit-isbn");
  const subjectsEl = $("#book-edit-subjects");
  const seriesIndexEl = $("#book-edit-series-index");

  const identifiersStatusEl = $("#book-edit-identifiers-status");
  const identifiersEl = $("#book-edit-identifiers");
  const identAddFormEl = $("#book-edit-identifiers-add");
  const identAddSchemeEl = $("#book-edit-ident-add-scheme");
  const identAddValueEl = $("#book-edit-ident-add-value");
  const identAddSourceEl = $("#book-edit-ident-add-source");
  const identAddPrimaryEl = $("#book-edit-ident-add-primary");
  const identAddStatusEl = $("#book-edit-identifiers-add-status");

  const groupsStatusEl = $("#book-edit-groups-status");
  const groupsEl = $("#book-edit-groups");
  const groupsAddFormEl = $("#book-edit-groups-add");
  const groupsAddSelectEl = $("#book-edit-groups-add-select");
  const groupsAddBtnEl = $("#book-edit-groups-add-btn");
  const groupsAddStatusEl = $("#book-edit-groups-add-status");

  if (
    !rootEl ||
    !statusEl ||
    !errorEl ||
    !savedEl ||
    !saveStatusEl ||
    !formEl ||
    !saveBtn ||
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
    !titleEl ||
    !subtitleEl ||
    !summaryEl ||
    !publisherEl ||
    !languageEl ||
    !publishedDateEl ||
    !isbnEl ||
    !subjectsEl ||
    !seriesIndexEl
    || !identifiersStatusEl
    || !identifiersEl
    || !identAddFormEl
    || !identAddSchemeEl
    || !identAddValueEl
    || !identAddSourceEl
    || !identAddPrimaryEl
    || !identAddStatusEl
    || !groupsStatusEl
    || !groupsEl
    || !groupsAddFormEl
    || !groupsAddSelectEl
    || !groupsAddBtnEl
    || !groupsAddStatusEl
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
    return;
  }

  setStatus("Loading…", false);
  setError("");
  setSaved(false);
  visible(rootEl, false);

  let original = null;
  let originalAuthorIds = [];
  let originalSeriesId = null;

  let selectedAuthors = [];
  let allAuthors = [];
  let allSeries = [];
  let identifiers = [];
  let groups = [];
  let allGroups = [];

  try {
    const book = await fetchJSON(`/api/v1/library/books/${encodeURIComponent(String(bookId))}/`);
    original = book;

    setText(statusEl, "");
    visible(rootEl, true);

    titleEl.value = book.title || "";
    subtitleEl.value = book.subtitle || "";
    summaryEl.value = book.summary || "";
    publisherEl.value = book.publisher || "";
    languageEl.value = book.language || "";
    publishedDateEl.value = book.published_date || "";
    isbnEl.value = book.isbn || "";
    subjectsEl.value = subjectsToTextareaValue(book.subjects);
    seriesIndexEl.value = book.series_index != null && book.series_index !== "" ? String(book.series_index) : "";

    selectedAuthors = uniqueById(Array.isArray(book.authors) ? book.authors : []);
    originalAuthorIds = selectedAuthors.map((a) => String(a.id)).filter(Boolean);
    originalSeriesId = book.series && book.series.id ? String(book.series.id) : null;
    identifiers = Array.isArray(book.identifiers) ? book.identifiers : [];
    groups = Array.isArray(book.groups) ? book.groups : [];
  } catch (e) {
    console.error("Failed to load book for edit", { bookId, e });
    if (e && e.status === 404) {
      setStatus("Book not found or not accessible.", true);
    } else {
      setStatus("Error loading book.", true);
      setGlobalErrorFromError(e, "Failed to load book:");
    }
    return;
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

  async function loadAuthorsAndSeries() {
    setInlineStatus(authorsStatusEl, "Loading…", false);
    setInlineStatus(seriesStatusEl, "Loading…", false);

    try {
      allAuthors = uniqueById(await fetchAllPages("/api/v1/library/authors/"));
      setInlineStatus(authorsStatusEl, `Loaded ${allAuthors.length}.`, false);
    } catch (e) {
      console.error("Failed to load authors", e);
      setInlineStatus(authorsStatusEl, "Failed to load.", true);
      setError(`Failed to load authors: ${extractApiErrorMessage(e)}`);
      allAuthors = [];
    }

    try {
      allSeries = uniqueById(await fetchAllPages("/api/v1/library/series/"));
      setInlineStatus(seriesStatusEl, `Loaded ${allSeries.length}.`, false);
    } catch (e2) {
      console.error("Failed to load series", e2);
      setInlineStatus(seriesStatusEl, "Failed to load.", true);
      setError(`Failed to load series: ${extractApiErrorMessage(e2)}`);
      allSeries = [];
    }

    renderSelectedAuthors();
    syncAuthorSelectOptions();
    syncSeriesSelectOptions(originalSeriesId);
  }

  await loadAuthorsAndSeries();

  function setGroupsStatus(text, isError) {
    setInlineStatus(groupsStatusEl, text, isError);
  }

  function setGroupsAddStatus(text, isError) {
    setInlineStatus(groupsAddStatusEl, text, isError);
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

  async function refreshBookGroups() {
    try {
      const book = await fetchJSON(`/api/v1/library/books/${encodeURIComponent(String(bookId))}/`);
      groups = Array.isArray(book.groups) ? book.groups : [];
      renderGroups();
      syncGroupsAddOptions();
    } catch (e) {
      console.error("Failed to refresh book groups", e);
      setGroupsStatus("Failed to refresh.", true);
      setError(`Failed to refresh book: ${extractApiErrorMessage(e)}`);
    }
  }

  async function loadAllGroups() {
    setGroupsStatus("Loading…", false);
    try {
      const payload = await fetchAllPages("/api/v1/library/groups/");
      allGroups = uniqueById(payload);
      setGroupsStatus("", false);
      renderGroups();
      syncGroupsAddOptions();
    } catch (e) {
      console.error("Failed to load groups list", e);
      setGroupsStatus("Failed to load.", true);
      setError(`Failed to load groups: ${extractApiErrorMessage(e)}`);
      allGroups = [];
      renderGroups();
      syncGroupsAddOptions();
    }
  }

  renderGroups();
  await loadAllGroups();

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

    setGroupsStatus("Removing…", false);
    try {
      await fetchJSONWithOptions(
        `/api/v1/library/groups/${encodeURIComponent(String(gid))}/books/${encodeURIComponent(String(bookId))}/`,
        { method: "DELETE", headers: { Accept: "application/json", "X-CSRFToken": csrf } }
      );
      setGroupsStatus("", false);
      await refreshBookGroups();
    } catch (e) {
      console.error("Remove group assignment failed", e);
      setGroupsStatus("Remove failed.", true);
      setError(`Failed to remove from group: ${extractApiErrorMessage(e)}`);
    }
  });

  groupsAddFormEl.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    setError("");
    setGroupsAddStatus("", false);

    const gid = (groupsAddSelectEl.value || "").trim();
    if (!gid) return;

    const csrf = getCsrfToken();
    if (!csrf) {
      setError("Missing CSRF token cookie. Reload the page and try again.");
      return;
    }

    setGroupsAddStatus("Adding…", false);
    try {
      await fetchJSONWithOptions(`/api/v1/library/groups/${encodeURIComponent(String(gid))}/books/`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": csrf,
        },
        body: JSON.stringify({ book: String(bookId) }),
      });
      setGroupsAddStatus("Added.", false);
      await refreshBookGroups();
    } catch (e) {
      console.error("Add group assignment failed", e);
      setGroupsAddStatus("Add failed.", true);
      const msg = extractApiErrorMessage(e);
      const body = e && e.body ? e.body : null;
      const fields = summarizeFieldErrors(body);
      setError(fields ? `${msg} (${fields})` : msg);
    }
  });

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

  identAddSchemeEl.innerHTML = schemeOptionsHtml("isbn_13");

  function setIdentifiersStatus(text, isError) {
    setInlineStatus(identifiersStatusEl, text, isError);
  }

  function setIdentifierAddStatus(text, isError) {
    setInlineStatus(identAddStatusEl, text, isError);
  }

  function renderIdentifiers() {
    if (!identifiers.length) {
      identifiersEl.innerHTML = '<div class="muted">No identifiers.</div>';
      return;
    }

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
          <div class="card" data-ident-id="${escapeHtml(id)}" style="margin: 10px 0;">
            <div class="kv">
              <div class="kv__k"><label>Scheme</label></div>
              <div class="kv__v"><select data-ident-field="scheme">${schemeOptionsHtml(scheme)}</select></div>

              <div class="kv__k"><label>Value</label></div>
              <div class="kv__v"><input data-ident-field="value" type="text" value="${escapeHtml(value)}" style="width: 100%;" /></div>

              <div class="kv__k"><label>Source</label></div>
              <div class="kv__v"><input data-ident-field="source" type="text" value="${escapeHtml(source)}" style="width: 100%;" /></div>

              <div class="kv__k"><label>Primary</label></div>
              <div class="kv__v"><input data-ident-field="is_primary" type="checkbox" ${primary ? "checked" : ""} /></div>
            </div>

            <div style="margin-top: 10px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
              <button class="button" type="button" data-ident-action="save">Save</button>
              <button class="button" type="button" data-ident-action="delete">Delete</button>
              <span class="muted" data-ident-status=""></span>
            </div>
          </div>
        `.trim();
      })
      .join("");

    identifiersEl.innerHTML = rows;
  }

  async function refreshIdentifiers() {
    setIdentifiersStatus("Loading…", false);
    try {
      const list = await fetchJSON(
        `/api/v1/library/books/${encodeURIComponent(String(bookId))}/identifiers/`
      );
      identifiers = Array.isArray(list) ? list : [];
      setIdentifiersStatus("", false);
      renderIdentifiers();
    } catch (e) {
      console.error("Failed to load identifiers", e);
      setIdentifiersStatus("Failed to load.", true);
      setError(`Failed to load identifiers: ${extractApiErrorMessage(e)}`);
    }
  }

  renderIdentifiers();
  refreshIdentifiers().catch(() => {});

  identifiersEl.addEventListener("click", async (ev) => {
    const t = ev.target;
    if (!t || !t.getAttribute) return;
    const action = t.getAttribute("data-ident-action");
    if (!action) return;

    const card = t.closest ? t.closest("[data-ident-id]") : null;
    if (!card) return;
    const identId = card.getAttribute("data-ident-id");
    if (!identId) return;

    const statusSpan = card.querySelector ? card.querySelector("[data-ident-status]") : null;
    const setRowStatus = (text, isError) => setInlineStatus(statusSpan, text, isError);

    const csrf = getCsrfToken();
    if (!csrf) {
      setError("Missing CSRF token cookie. Reload the page and try again.");
      return;
    }

    if (action === "delete") {
      setRowStatus("Deleting…", false);
      try {
        await fetchJSONWithOptions(
          `/api/v1/library/books/${encodeURIComponent(String(bookId))}/identifiers/${encodeURIComponent(
            String(identId)
          )}/`,
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
      const schemeEl = card.querySelector('[data-ident-field="scheme"]');
      const valueEl = card.querySelector('[data-ident-field="value"]');
      const sourceEl = card.querySelector('[data-ident-field="source"]');
      const primaryEl = card.querySelector('[data-ident-field="is_primary"]');

      const payload = {
        scheme: schemeEl && schemeEl.value != null ? String(schemeEl.value) : "",
        value: valueEl && valueEl.value != null ? String(valueEl.value) : "",
        source: sourceEl && sourceEl.value != null ? String(sourceEl.value) : "",
        is_primary: !!(primaryEl && primaryEl.checked),
      };

      setRowStatus("Saving…", false);
      try {
        await fetchJSONWithOptions(
          `/api/v1/library/books/${encodeURIComponent(String(bookId))}/identifiers/${encodeURIComponent(
            String(identId)
          )}/`,
          {
            method: "PATCH",
            headers: {
              Accept: "application/json",
              "Content-Type": "application/json",
              "X-CSRFToken": csrf,
            },
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

  identAddFormEl.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    setError("");
    setIdentifierAddStatus("", false);

    const scheme = (identAddSchemeEl.value || "").trim();
    const value = (identAddValueEl.value || "").trim();
    const source = (identAddSourceEl.value || "").trim();
    const isPrimary = !!identAddPrimaryEl.checked;

    if (!scheme) {
      setError("Scheme is required.");
      return;
    }
    if (!value) {
      setError("Value is required.");
      return;
    }

    const csrf = getCsrfToken();
    if (!csrf) {
      setError("Missing CSRF token cookie. Reload the page and try again.");
      return;
    }

    setIdentifierAddStatus("Adding…", false);
    try {
      await fetchJSONWithOptions(
        `/api/v1/library/books/${encodeURIComponent(String(bookId))}/identifiers/`,
        {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
            "X-CSRFToken": csrf,
          },
          body: JSON.stringify({ scheme, value, source, is_primary: isPrimary }),
        }
      );
      identAddValueEl.value = "";
      identAddPrimaryEl.checked = false;
      setIdentifierAddStatus("Added.", false);
      await refreshIdentifiers();
    } catch (e) {
      console.error("Add identifier failed", e);
      setIdentifierAddStatus("Add failed.", true);
      const msg = extractApiErrorMessage(e);
      const body = e && e.body ? e.body : null;
      const fields = summarizeFieldErrors(body);
      setError(fields ? `${msg} (${fields})` : msg);
    }
  });

  authorsSelectedEl.addEventListener("click", (ev) => {
    const t = ev.target;
    if (!t || !t.getAttribute) return;
    const id = t.getAttribute("data-remove-author-id");
    if (!id) return;
    selectedAuthors = selectedAuthors.filter((a) => String(a.id) !== String(id));
    renderSelectedAuthors();
    syncAuthorSelectOptions();
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
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": csrf,
        },
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
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": csrf,
        },
        body: JSON.stringify({ name }),
      });
      allSeries.push(created);
      allSeries = uniqueById(allSeries);
      seriesNewNameEl.value = "";
      setInlineStatus(seriesStatusEl, "Created.", false);
      const createdId = created && created.id ? String(created.id) : "";
      syncSeriesSelectOptions(createdId);
    } catch (e2) {
      console.error("Failed to create series", e2);
      setInlineStatus(seriesStatusEl, "Create failed.", true);
      setError(`Failed to create series: ${extractApiErrorMessage(e2)}`);
    }
  });

  async function save() {
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

    const payload = {
      title,
      // Book.subtitle is a CharField(blank=True); allow explicit empty string.
      subtitle: (subtitleEl.value || "").trim(),
      summary: normalizeOptionalString(summaryEl.value),
      publisher: normalizeOptionalString(publisherEl.value),
      language: normalizeOptionalString(languageEl.value),
      published_date: publishedDate,
      isbn: normalizeOptionalString(isbnEl.value),
      subjects: normalizeSubjects(subjectsEl.value),
      authors: selectedAuthors.map((a) => String(a.id)).filter(Boolean),
      series: seriesSelectEl.value ? String(seriesSelectEl.value) : null,
      series_index: normalizeSeriesIndex(seriesIndexEl.value),
    };
    if (payload.series_index && typeof payload.series_index === "object" && payload.series_index.error) {
      setError(payload.series_index.error);
      return;
    }

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
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": csrf,
        },
        body: JSON.stringify(patch),
      });

      original = updated;
      originalAuthorIds = payload.authors;
      originalSeriesId = payload.series;

      setSaved(true);
      setText(saveStatusEl, "");

      window.setTimeout(() => {
        window.location.href = `/library/books/${encodeURIComponent(String(bookId))}/`;
      }, 650);
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
    save().catch((e) => {
      console.error("save failed", e);
      setError(extractApiErrorMessage(e));
    });
  });
}
