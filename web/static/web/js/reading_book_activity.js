import { fetchJSON, patchJSON, extractApiErrorMessage, summarizeFieldErrors } from "./api.js";
import { $, loadMeAndInitShell, setGlobalErrorFromError, visible } from "./layout.js";
import { mountCovers } from "./ui/covers.js";

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

function formatWhen(value) {
  if (!value) return "";
  const d = new Date(String(value));
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function parseSearchParams() {
  try {
    return new URLSearchParams(window.location.search);
  } catch {
    return new URLSearchParams();
  }
}

function renderBookMeta(container, book) {
  clear(container);
  const title = book && book.title ? String(book.title) : "Book";
  const subtitle = book && book.subtitle ? String(book.subtitle) : "";
  const authors = Array.isArray(book && book.authors) ? book.authors.map((a) => a && a.name).filter(Boolean) : [];
  const series = book && book.series && book.series.name ? String(book.series.name) : "";
  const seriesIndex = book && book.series_index != null && book.series_index !== "" ? String(book.series_index) : "";

  const wrap = document.createElement("div");
  wrap.className = "book-meta";

  wrap.appendChild(el("div", "book-meta__line", title));
  if (subtitle) wrap.appendChild(el("div", "muted", subtitle));
  if (authors.length) wrap.appendChild(el("div", "book-meta__line", authors.join(", ")));
  if (series) wrap.appendChild(el("div", "muted", `${series}${seriesIndex ? ` #${seriesIndex}` : ""}`));

  container.appendChild(wrap);
}

async function tryGetSession(sessionId) {
  if (!sessionId) return null;
  try {
    return await fetchJSON(`/api/v1/reading/sessions/${encodeURIComponent(String(sessionId))}/`);
  } catch (e) {
    return null;
  }
}

async function getActiveSessionForBook(bookId) {
  try {
    return await fetchJSON(`/api/v1/reading/books/${encodeURIComponent(String(bookId))}/active-session/`);
  } catch (e) {
    return null;
  }
}

async function getProgressForSession(sessionId) {
  return await fetchJSON(`/api/v1/reading/sessions/${encodeURIComponent(String(sessionId))}/progress/`);
}

async function getAnnotationsForBook(bookId) {
  // Keep it simple for v1: grab up to 200 and sort client-side.
  const payload = await fetchJSON(`/api/v1/reading/annotations/?book_id=${encodeURIComponent(String(bookId))}&page_size=200`);
  return payload && Array.isArray(payload.results) ? payload.results : Array.isArray(payload) ? payload : [];
}

function sortAnnotations(rows, sortKey) {
  const arr = Array.isArray(rows) ? rows.slice() : [];
  arr.sort((a, b) => {
    const au = a && a.updated_at ? new Date(String(a.updated_at)).getTime() : 0;
    const bu = b && b.updated_at ? new Date(String(b.updated_at)).getTime() : 0;
    return sortKey === "oldest" ? au - bu : bu - au;
  });
  return arr;
}

function renderAnnotationRow(a) {
  const wrap = document.createElement("article");
  wrap.className = "card";

  const motivation = a && a.motivation ? String(a.motivation) : "";
  const updatedAt = a && a.updated_at ? String(a.updated_at) : "";
  const createdAt = a && a.created_at ? String(a.created_at) : "";
  const sessionId = a && a.session ? String(a.session) : "";

  const header = el("div", "muted", "");
  const metaBits = [];
  if (motivation) metaBits.push(motivation);
  if (updatedAt) metaBits.push(`Updated ${formatWhen(updatedAt)}`);
  else if (createdAt) metaBits.push(`Created ${formatWhen(createdAt)}`);
  if (sessionId) metaBits.push(`Session ${sessionId}`);
  header.textContent = metaBits.join(" - ");
  wrap.appendChild(header);

  const bodies = Array.isArray(a && a.body) ? a.body : [];
  const highlight = bodies.find((b) => b && b.type === "TextualBody" && (b.purpose === "describing" || b.purpose === "highlighting"));
  const comment = bodies.find((b) => b && b.type === "TextualBody" && b.purpose === "commenting");

  if (highlight && (highlight.value || highlight.color)) {
    const v = typeof highlight.value === "string" ? highlight.value : "";
    const line = el("div", "", v);
    wrap.appendChild(line);
  }
  if (comment && comment.value) {
    const v = typeof comment.value === "string" ? comment.value : "";
    const line = el("div", "", v);
    wrap.appendChild(line);
  }

  if (!wrap.textContent || !wrap.textContent.trim()) {
    wrap.appendChild(el("div", "muted", "(Empty annotation)"));
  }

  return wrap;
}

function renderAnnotations(container, rows, sortKey) {
  clear(container);
  const sorted = sortAnnotations(rows, sortKey);
  if (!sorted.length) {
    container.appendChild(el("div", "muted", "No annotations yet."));
    return;
  }
  for (const a of sorted) {
    container.appendChild(renderAnnotationRow(a));
  }
}

export async function initReadingBookActivity() {
  await loadMeAndInitShell();

  const statusEl = $("#reading-activity-status");
  const errEl = $("#reading-activity-error");
  const root = $("#reading-activity");
  const titleEl = $("#reading-activity-title");
  const subtitleEl = $("#reading-activity-subtitle");
  const bookMetaEl = $("#reading-activity-book-meta");
  const coverEl = $("#reading-activity-cover");
  const sessionEl = $("#reading-activity-session");
  const sessionNameEl = $("#reading-activity-session-name");
  const sessionSaveBtn = $("#reading-activity-session-save");
  const sessionSaveStatusEl = $("#reading-activity-session-save-status");
  const sessionIdEl = $("#reading-activity-session-id");
  const progressEl = $("#reading-activity-progress");
  const annEl = $("#reading-activity-annotations");
  const sortEl = $("#reading-activity-sort");

  if (
    !statusEl ||
    !errEl ||
    !root ||
    !titleEl ||
    !subtitleEl ||
    !bookMetaEl ||
    !coverEl ||
    !sessionEl ||
    !sessionNameEl ||
    !sessionSaveBtn ||
    !sessionSaveStatusEl ||
    !sessionIdEl ||
    !progressEl ||
    !annEl ||
    !sortEl
  )
    return;

  function setErr(msg) {
    errEl.textContent = msg || "";
    visible(errEl, !!msg);
  }

  const bookId = root.dataset ? root.dataset.bookId : "";
  if (!bookId) {
    statusEl.textContent = "Missing book id.";
    statusEl.classList.add("error");
    return;
  }

  statusEl.textContent = "Loading...";
  setErr("");
  visible(root, false);

  try {
    const book = await fetchJSON(`/api/v1/library/books/${encodeURIComponent(String(bookId))}/`);
    const titleText = book && book.title ? String(book.title) : "Reading activity";
    titleEl.textContent = "Reading activity";
    subtitleEl.textContent = titleText;

    const coverUrl = book && book.cover_url ? String(book.cover_url) : "";
    coverEl.dataset.coverUrl = coverUrl;
    coverEl.dataset.coverTitle = titleText;
    mountCovers(coverEl.parentNode);

    renderBookMeta(bookMetaEl, book);

    const params = parseSearchParams();
    const preferredSessionId = (params.get("session") || "").trim();
    let session = null;

    if (preferredSessionId) {
      const maybe = await tryGetSession(preferredSessionId);
      if (maybe && String(maybe.book) === String(bookId)) session = maybe;
    }
    if (!session) {
      session = await getActiveSessionForBook(bookId);
    }

    let sessionId = "";
    let sessionName = "";
    if (session && session.id) {
      sessionId = String(session.id);
      sessionName = session && typeof session.name === "string" ? session.name : "";
      sessionIdEl.textContent = `Session ${sessionId}`;
      sessionNameEl.value = sessionName;
      sessionSaveBtn.disabled = true;
      sessionSaveStatusEl.textContent = "";
      try {
        const progress = await getProgressForSession(sessionId);
        const progression = progress && progress.progression != null ? Number(progress.progression) : null;
        progressEl.textContent =
          progression != null && Number.isFinite(progression)
            ? `Progression: ${Math.round(progression * 1000) / 10}%`
            : "No progress yet.";
      } catch (e2) {
        progressEl.textContent = "No progress yet.";
      }
    } else {
      sessionIdEl.textContent = "No session.";
      sessionNameEl.value = "";
      sessionSaveBtn.disabled = true;
      sessionSaveStatusEl.textContent = "";
      progressEl.textContent = "No progress yet.";
    }

    function updateSaveButtonState() {
      if (!sessionId) {
        sessionSaveBtn.disabled = true;
        return;
      }
      const current = (sessionNameEl.value || "").trim();
      const original = (sessionName || "").trim();
      sessionSaveBtn.disabled = current === original;
    }

    sessionNameEl.addEventListener("input", () => {
      sessionSaveStatusEl.textContent = "";
      updateSaveButtonState();
    });

    sessionSaveBtn.addEventListener("click", async () => {
      if (!sessionId) return;
      const desired = (sessionNameEl.value || "").trim();

      sessionSaveBtn.disabled = true;
      sessionSaveStatusEl.textContent = "Saving...";
      try {
        const updated = await patchJSON(`/api/v1/reading/sessions/${encodeURIComponent(sessionId)}/`, { name: desired });
        sessionName = updated && typeof updated.name === "string" ? updated.name : desired;
        sessionNameEl.value = sessionName;
        sessionSaveStatusEl.textContent = "Saved.";
      } catch (eSave) {
        const msg = extractApiErrorMessage(eSave);
        const fields = summarizeFieldErrors(eSave && eSave.body ? eSave.body : null);
        sessionSaveStatusEl.textContent = fields ? `${msg} (${fields})` : msg;
      } finally {
        updateSaveButtonState();
      }
    });

    let annotations = [];
    try {
      annotations = await getAnnotationsForBook(bookId);
    } catch (e3) {
      console.error("Failed to load annotations", e3);
      annotations = [];
    }

    function rerender() {
      const key = (sortEl.value || "newest").toLowerCase() === "oldest" ? "oldest" : "newest";
      renderAnnotations(annEl, annotations, key);
    }

    sortEl.addEventListener("change", rerender);
    rerender();

    statusEl.textContent = "";
    visible(root, true);
  } catch (e) {
    console.error("Failed to load reading activity", e);
    statusEl.textContent = "Error loading reading activity.";
    setErr("Could not load reading activity.");
    setGlobalErrorFromError(e, "Failed to load reading activity:");
  }
}
