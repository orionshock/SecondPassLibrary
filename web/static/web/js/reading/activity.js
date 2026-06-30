import { fetchJSON, fetchJSONWithOptions, getCsrfToken, patchJSON, extractApiErrorMessage, summarizeFieldErrors } from "../api.js";
import { $, loadMeAndInitShell, setGlobalErrorFromError, visible } from "../layout.js";
import { setBreadcrumbs } from "../ui/breadcrumbs.js";
import { mountCovers } from "../ui/covers.js";
import { bindSessionControls, renderSessionDisplay, sessionIsWritable } from "./activity_actions.js";
import { renderAnnotations, renderBookMeta } from "./activity_rendering.js";

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

function sessionBreadcrumbLabel(state) {
  const name = state && state.sessionName ? String(state.sessionName).trim() : "";
  return name || "Session";
}

function syncActivityBreadcrumb({ bookId, bookTitle, sessionState }) {
  setBreadcrumbs([
    { label: "My Marginalia", href: "/app/" },
    {
      label: bookTitle || "Book",
      href: `/reading/sessions/books/${encodeURIComponent(String(bookId))}/`,
    },
    { label: sessionBreadcrumbLabel(sessionState), current: true },
  ]);
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
    syncActivityBreadcrumb({ bookId, bookTitle: titleText, sessionState: null });
    titleEl.textContent = `Marginalia for \u201c${titleText}\u201d`;
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

    const sessionState = {
      sessionId: "",
      sessionName: "",
      sessionStatus: "",
      sessionIsActive: false,
      canEditSessionMetadata: false,
    };

    if (session && session.id) {
      sessionState.sessionId = String(session.id);
      sessionState.sessionName = session && typeof session.name === "string" ? session.name : "";
      sessionIdEl.textContent = `Session ID: ${sessionState.sessionId}`;

      sessionState.sessionStatus = session && typeof session.status === "string" ? session.status : "";
      sessionState.sessionIsActive = !!(session && session.is_active);
      sessionState.canEditSessionMetadata = sessionIsWritable(sessionState);
      renderSessionDisplay(sessionDisplayEl, sessionState);
      syncActivityBreadcrumb({ bookId, bookTitle: titleText, sessionState });

      sessionNameEl.value = sessionState.sessionName;
      sessionSaveBtn.disabled = true;
      sessionSaveStatusEl.textContent = "";
      try {
        const progress = await getProgressForSession(sessionState.sessionId);
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
      sessionState.sessionStatus = "";
      sessionState.sessionIsActive = false;
    }

    bindSessionControls({
      elements: {
        sessionDisplayEl,
        sessionEditBtn,
        sessionEditFormEl,
        sessionNameEl,
        sessionSaveBtn,
        sessionSaveStatusEl,
        sessionCancelBtn,
        sessionCloseBtn,
        sessionCloseStatusEl,
      },
      state: sessionState,
      visible,
      patchSessionName: (targetSessionId, name) =>
        patchJSON(`/api/v1/reading/sessions/${encodeURIComponent(targetSessionId)}/`, { name }),
      closeSessionById: closeSession,
      extractApiErrorMessage,
      summarizeFieldErrors,
      onSessionChanged: () => syncActivityBreadcrumb({ bookId, bookTitle: titleText, sessionState }),
    });

    let annotations = [];
    try {
      annotations = await getAnnotationsForSession(sessionState.sessionId);
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
