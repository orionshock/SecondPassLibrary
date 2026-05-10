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

export async function initBookEdit() {
  const me = await loadMeAndInitShell();

  const rootEl = $("#book-edit");
  const statusEl = $("#book-edit-status");
  const errorEl = $("#book-edit-error");
  const savedEl = $("#book-edit-saved");
  const saveStatusEl = $("#book-edit-save-status");
  const formEl = $("#book-edit-form");
  const saveBtn = $("#book-edit-save");
  const authorsSeriesEl = $("#book-edit-authors-series");

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
    !authorsSeriesEl ||
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

    const authors = Array.isArray(book.authors) ? book.authors.map((a) => a && a.name).filter(Boolean) : [];
    const series = book.series && book.series.name ? String(book.series.name) : "";
    const seriesLine = series ? `${series}${book.series_index != null && book.series_index !== "" ? " Â· " + book.series_index : ""}` : "";

    authorsSeriesEl.innerHTML = `
      <div class="kv">
        <div class="kv__k">Authors</div><div class="kv__v">${escapeHtml(authors.join(", ") || "")}</div>
        <div class="kv__k">Series</div><div class="kv__v">${escapeHtml(seriesLine)}</div>
      </div>
    `.trim();
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
      series_index: normalizeOptionalString(seriesIndexEl.value) ? Number(seriesIndexEl.value) : null,
    };

    // Avoid sending NaN
    if (payload.series_index != null && !Number.isFinite(payload.series_index)) payload.series_index = null;

    // Drop unchanged fields to reduce accidental overwrites.
    const patch = {};
    for (const [k, v] of Object.entries(payload)) {
      const oldVal = original ? original[k] : undefined;
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
