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
      subtitle: normalizeOptionalString(subtitleEl.value),
      summary: normalizeOptionalString(summaryEl.value),
      publisher: normalizeOptionalString(publisherEl.value),
      language: normalizeOptionalString(languageEl.value),
      published_date: publishedDate,
      isbn: normalizeOptionalString(isbnEl.value),
      subjects: normalizeSubjects(subjectsEl.value),
      authors: selectedAuthors.map((a) => String(a.id)).filter(Boolean),
      series: seriesSelectEl.value ? String(seriesSelectEl.value) : null,
      series_index: normalizeOptionalString(seriesIndexEl.value) ? Number(seriesIndexEl.value) : null,
    };

    if (payload.series_index != null && !Number.isFinite(payload.series_index)) payload.series_index = null;

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

