import { fetchJSON, fetchJSONWithOptions, getCsrfToken, patchJSON, extractApiErrorMessage, summarizeFieldErrors } from "./api.js";
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

async function getSession(sessionId) {
  if (!sessionId) throw new Error("Missing session id");
  return await fetchJSON(`/api/v1/reading/sessions/${encodeURIComponent(String(sessionId))}/`);
}

async function getProgressForSession(sessionId) {
  return await fetchJSON(`/api/v1/reading/sessions/${encodeURIComponent(String(sessionId))}/progress/`);
}

async function closeSession(sessionId) {
  const csrf = getCsrfToken();
  return await fetchJSONWithOptions(`/api/v1/reading/sessions/${encodeURIComponent(String(sessionId))}/close/`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      ...(csrf ? { "X-CSRFToken": csrf } : {}),
    },
  });
}

async function getAnnotationsForSession(sessionId) {
  // Keep it simple for v1: grab up to 200 and sort client-side.
  const payload = await fetchJSON(
    `/api/v1/reading/annotations/?session_id=${encodeURIComponent(String(sessionId))}&page_size=200`,
  );
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
  wrap.className = "card annotation-card";

  const updatedAt = a && a.updated_at ? String(a.updated_at) : "";
  const createdAt = a && a.created_at ? String(a.created_at) : "";

  const bodies = Array.isArray(a && a.body) ? a.body : [];
  const quoteBody = bodies.find((b) => b && b.type === "TextualBody" && b.purpose === "describing");
  const noteBody = bodies.find((b) => b && b.type === "TextualBody" && b.purpose === "commenting");

  const quoteText = quoteBody && typeof quoteBody.value === "string" ? quoteBody.value : "";
  const noteText = noteBody && typeof noteBody.value === "string" ? noteBody.value : "";
  const hasQuote = !!quoteText;
  const hasNote = !!noteText;
  const motivation = a && a.motivation ? String(a.motivation) : "";
  const selectorValue =
    a && a.target && a.target.selector && typeof a.target.selector.value === "string"
      ? a.target.selector.value
      : "";
  const isBookmarkOnly = motivation === "bookmarking" && !hasQuote && !hasNote;

  let kindLabel = "Annotation";
  let kindIcon = "edit_note";
  if (isBookmarkOnly) {
    kindLabel = "Bookmark";
    kindIcon = "bookmark";
  } else if (hasQuote && hasNote) {
    kindLabel = "Highlight with note";
    kindIcon = "chat_bubble";
  } else if (hasNote && !hasQuote) {
    kindLabel = "Annotation";
    kindIcon = "edit_note";
  } else if (hasQuote && !hasNote) {
    kindLabel = "Highlight";
    kindIcon = "border_color";
  }

  const bodyWrap = document.createElement("div");
  bodyWrap.className = "annotation-card__body";

  const iconWrap = document.createElement("div");
  iconWrap.className = "annotation-card__icon";
  const icon = el("span", "material-symbols-outlined", kindIcon);
  icon.setAttribute("title", kindLabel);
  icon.setAttribute("aria-hidden", "true");
  iconWrap.appendChild(icon);
  iconWrap.appendChild(el("span", "sr-only", kindLabel));

  const contentWrap = document.createElement("div");
  contentWrap.className = "annotation-card__content";

  if (quoteText) {
    let token = quoteBody && typeof quoteBody.color === "string" ? quoteBody.color : "";
    token = (token || "").trim().toLowerCase();
    const allowed = new Set(["yellow", "green", "blue", "pink", "purple", "orange"]);
    if (!token || !allowed.has(token)) token = "yellow";

    const quoteEl = el("div", `annotation-quote annotation-quote--${token}`, quoteText);
    contentWrap.appendChild(quoteEl);
  }

  if (noteText) {
    const noteEl = el("div", "annotation-note", noteText);
    contentWrap.appendChild(noteEl);
  }

  if (isBookmarkOnly) {
    const titleEl = el("div", "", "Bookmark");
    const locationEl = el("div", "muted", "Saved location");
    if (selectorValue) {
      titleEl.setAttribute("title", selectorValue);
      locationEl.setAttribute("title", selectorValue);
    }
    contentWrap.appendChild(titleEl);
    contentWrap.appendChild(locationEl);
  } else if (!quoteText && !noteText) {
    const fallback = selectorValue ? selectorValue : "Bookmark";
    contentWrap.appendChild(el("div", "muted", fallback));
  }

  const whenText = updatedAt ? formatWhen(updatedAt) : createdAt ? formatWhen(createdAt) : "";
  contentWrap.appendChild(el("div", "muted annotation-meta", whenText));

  bodyWrap.appendChild(iconWrap);
  bodyWrap.appendChild(contentWrap);
  wrap.appendChild(bodyWrap);

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
  const sessionContextEl = $("#reading-activity-session-context");
  const sessionDisplayEl = $("#reading-activity-session-display");
  const sessionEditBtn = $("#reading-activity-session-edit");
  const sessionEditFormEl = $("#reading-activity-session-edit-form");
  const bookMetaEl = $("#reading-activity-book-meta");
  const coverEl = $("#reading-activity-cover");
  const sessionEl = $("#reading-activity-session");
  const sessionNameEl = $("#reading-activity-session-name");
  const sessionSaveBtn = $("#reading-activity-session-save");
  const sessionSaveStatusEl = $("#reading-activity-session-save-status");
  const sessionCancelBtn = $("#reading-activity-session-cancel");
  const sessionCloseBtn = $("#reading-activity-session-close");
  const sessionCloseStatusEl = $("#reading-activity-session-close-status");
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
    !sessionContextEl ||
    !sessionDisplayEl ||
    !sessionEditBtn ||
    !sessionEditFormEl ||
    !bookMetaEl ||
    !coverEl ||
    !sessionEl ||
    !sessionNameEl ||
    !sessionSaveBtn ||
    !sessionSaveStatusEl ||
    !sessionCancelBtn ||
    !sessionCloseBtn ||
    !sessionCloseStatusEl ||
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
  const initialSessionId = root.dataset ? root.dataset.sessionId : "";
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
    const titleText = book && book.title ? String(book.title) : "Book";
    titleEl.textContent = `Marginalia for “${titleText}”`;
    subtitleEl.textContent = "";
    sessionDisplayEl.textContent = "";
    visible(sessionEditFormEl, false);

    const coverUrl = book && book.cover_url ? String(book.cover_url) : "";
    coverEl.dataset.coverUrl = coverUrl;
    coverEl.dataset.coverTitle = titleText;
    mountCovers(coverEl.parentNode);

    renderBookMeta(bookMetaEl, book);

    const preferredSessionId = (initialSessionId || "").trim();
    if (!preferredSessionId) {
      statusEl.textContent = "Invalid session ID.";
      setErr("Invalid session ID.");
      return;
    }

    let session = null;
    try {
      session = await getSession(preferredSessionId);
    } catch (eSession) {
      statusEl.textContent = "Invalid session ID.";
      setErr("Invalid session ID.");
      return;
    }

    const sessionBookId =
      session && session.book_id
        ? String(session.book_id)
        : session && session.book && typeof session.book === "object" && session.book.id
          ? String(session.book.id)
          : session && session.book
            ? String(session.book)
            : "";
    if (!sessionBookId || sessionBookId !== String(bookId)) {
      statusEl.textContent = "Invalid session ID.";
      setErr("Invalid session ID.");
      return;
    }

    let sessionId = "";
    let sessionName = "";
    let sessionStatus = "";
    let sessionIsActive = false;
    let canEditSessionMetadata = false;

    function sessionIsWritable() {
      return sessionStatus === "active" && sessionIsActive === true;
    }

    function renderSessionDisplay() {
      const sessionDisplayName = sessionName && sessionName.trim() ? sessionName.trim() : sessionId;
      if (!sessionDisplayName) {
        sessionDisplayEl.textContent = "";
        return;
      }
      const suffix = sessionIsWritable() ? "" : ` (${sessionStatus || "closed"})`;
      sessionDisplayEl.textContent = `Session: "${sessionDisplayName}"${suffix}`;
    }

    if (session && session.id) {
      sessionId = String(session.id);
      sessionName = session && typeof session.name === "string" ? session.name : "";
      sessionIdEl.textContent = `Session ID: ${sessionId}`;

      sessionStatus = session && typeof session.status === "string" ? session.status : "";
      sessionIsActive = !!(session && session.is_active);
      canEditSessionMetadata = sessionIsWritable();
      renderSessionDisplay();

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
      sessionDisplayEl.textContent = "";
      sessionNameEl.value = "";
      sessionSaveBtn.disabled = true;
      sessionSaveStatusEl.textContent = "";
      progressEl.textContent = "No progress yet.";
      sessionStatus = "";
      sessionIsActive = false;
    }

    function enterEditMode() {
      if (!sessionId) return;
      sessionSaveStatusEl.textContent = "";
      sessionNameEl.value = sessionName;
      visible(sessionEditBtn, false);
      visible(sessionEditFormEl, true);
      sessionNameEl.focus();
      sessionNameEl.select();
      updateSaveButtonState();
    }

    function exitEditMode() {
      visible(sessionEditFormEl, false);
      visible(sessionEditBtn, !!sessionId && canEditSessionMetadata);
      sessionSaveStatusEl.textContent = "";
      sessionNameEl.value = sessionName;
      updateSaveButtonState();
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

    sessionEditBtn.addEventListener("click", () => enterEditMode());
    sessionCancelBtn.addEventListener("click", () => exitEditMode());

    // Initial UI: display mode when a session exists.
    visible(sessionEditBtn, !!sessionId && canEditSessionMetadata);
    visible(sessionEditFormEl, false);
    visible(sessionCloseBtn, !!sessionId && sessionIsWritable());
    sessionCloseStatusEl.textContent = "";

    sessionSaveBtn.addEventListener("click", async () => {
      if (!sessionId) return;
      const desired = (sessionNameEl.value || "").trim();

      sessionSaveBtn.disabled = true;
      sessionSaveStatusEl.textContent = "Saving...";
      try {
        const updated = await patchJSON(`/api/v1/reading/sessions/${encodeURIComponent(sessionId)}/`, { name: desired });
        sessionName = updated && typeof updated.name === "string" ? updated.name : desired;
        sessionNameEl.value = sessionName;
        renderSessionDisplay();
        sessionSaveStatusEl.textContent = "Saved.";
        // Return to display mode after a successful save.
        exitEditMode();
      } catch (eSave) {
        const msg = extractApiErrorMessage(eSave);
        const fields = summarizeFieldErrors(eSave && eSave.body ? eSave.body : null);
        sessionSaveStatusEl.textContent = fields ? `${msg} (${fields})` : msg;
      } finally {
        updateSaveButtonState();
      }
    });

    sessionCloseBtn.addEventListener("click", async () => {
      if (!sessionId || !sessionIsWritable()) return;
      const message = (sessionName || "").trim()
        ? "Close this reading session? Closed sessions cannot be edited."
        : "This session has no name. Closed sessions cannot be renamed later. Close anyway?";
      if (!window.confirm(message)) return;

      sessionCloseBtn.disabled = true;
      sessionCloseStatusEl.textContent = "Closing...";
      try {
        const closed = await closeSession(sessionId);
        sessionStatus = closed && typeof closed.status === "string" ? closed.status : "completed";
        sessionIsActive = !!(closed && closed.is_active);
        sessionName = closed && typeof closed.name === "string" ? closed.name : sessionName;
        sessionNameEl.value = sessionName;
        canEditSessionMetadata = false;
        renderSessionDisplay();
        visible(sessionEditBtn, false);
        visible(sessionEditFormEl, false);
        visible(sessionCloseBtn, false);
        sessionCloseStatusEl.textContent = "Session closed.";
      } catch (eClose) {
        sessionCloseStatusEl.textContent = extractApiErrorMessage(eClose);
        sessionCloseBtn.disabled = false;
      }
    });

    let annotations = [];
    try {
      annotations = await getAnnotationsForSession(sessionId);
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
