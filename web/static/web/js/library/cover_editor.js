import {
  fetchJSONWithOptions,
  getCsrfToken,
  summarizeFieldErrors,
} from "../api.js";
import { $, setText, visible } from "../layout.js";
import { setStatus } from "../ui/status.js";

const MAX_ERROR_LENGTH = 240;

export function cacheBustedCoverUrl(url) {
  const value = String(url || "");
  if (!value) return "";
  return `${value}${value.includes("?") ? "&" : "?"}cover_v=${Date.now()}`;
}

export function coverMutationError(error, fallback) {
  const body = error && error.body && typeof error.body === "object" ? error.body : null;
  const fields = summarizeFieldErrors(body);
  if (fields) return boundedSafeMessage(fields, fallback);
  const envelope = body && body.error && typeof body.error === "object" ? body.error : null;
  const message = envelope && envelope.message ? envelope.message : body && body.detail;
  return message ? boundedSafeMessage(message, fallback) : fallback;
}

function boundedSafeMessage(message, fallback) {
  const text = String(message || "").trim();
  if (!text || /<\s*(?:!doctype|\/?[a-z][^>]*)>|traceback/i.test(text)) return fallback;
  return text.slice(0, MAX_ERROR_LENGTH);
}

export function initBookCoverEditor({ bookId, onCoverChanged }) {
  const openButton = $("#book-cover-edit");
  const modal = $("#book-cover-modal");
  const form = $("#book-cover-form");
  const fileInput = $("#book-cover-file");
  const selection = $("#book-cover-selection");
  const previewWrap = $("#book-cover-preview-wrap");
  const preview = $("#book-cover-preview");
  const statusEl = $("#book-cover-editor-status");
  const submitButton = $("#book-cover-submit");
  const clearButton = $("#book-cover-clear");
  const cancelButton = $("#book-cover-cancel");
  if (
    !openButton ||
    !modal ||
    !form ||
    !fileInput ||
    !selection ||
    !previewWrap ||
    !preview ||
    !statusEl ||
    !submitButton ||
    !clearButton ||
    !cancelButton
  )
    return null;

  let currentCoverUrl = "";
  let previewUrl = "";

  function discardPreview() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = "";
    preview.removeAttribute("src");
    visible(previewWrap, false);
  }

  function resetSelection() {
    discardPreview();
    fileInput.value = "";
    setText(selection, "No image selected.");
  }

  function setBusy(busy) {
    fileInput.disabled = busy;
    submitButton.disabled = busy;
    clearButton.disabled = busy || !currentCoverUrl;
    cancelButton.disabled = busy;
  }

  function close() {
    resetSelection();
    setStatus(statusEl, "", false);
    modal.hidden = true;
  }

  openButton.addEventListener("click", () => {
    resetSelection();
    setStatus(statusEl, "", false);
    setBusy(false);
    modal.hidden = false;
    fileInput.focus();
  });

  fileInput.addEventListener("change", () => {
    discardPreview();
    const file = fileInput.files && fileInput.files[0];
    setText(selection, file ? file.name : "No image selected.");
    if (!file) return;
    previewUrl = URL.createObjectURL(file);
    preview.src = previewUrl;
    visible(previewWrap, true);
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = fileInput.files && fileInput.files[0];
    if (!file) {
      setStatus(statusEl, "Choose a cover image.", true);
      return;
    }

    const data = new FormData();
    data.append("cover", file);
    const csrf = getCsrfToken();
    setBusy(true);
    setStatus(statusEl, "Uploading...", false);
    try {
      const book = await fetchJSONWithOptions(
        `/api/v1/library/books/${encodeURIComponent(String(bookId))}/cover/`,
        {
          method: "POST",
          headers: { Accept: "application/json", ...(csrf ? { "X-CSRFToken": csrf } : {}) },
          body: data,
        }
      );
      currentCoverUrl = cacheBustedCoverUrl(book && book.cover_url);
      onCoverChanged(currentCoverUrl);
      resetSelection();
      setStatus(statusEl, "Cover updated.", false);
    } catch (error) {
      console.error("Failed to replace book cover", { bookId, error });
      setStatus(statusEl, coverMutationError(error, "Cover could not be updated."), true);
    } finally {
      setBusy(false);
    }
  });

  clearButton.addEventListener("click", async () => {
    if (!currentCoverUrl || !window.confirm("Clear this cover?")) return;
    const csrf = getCsrfToken();
    setBusy(true);
    setStatus(statusEl, "Clearing...", false);
    try {
      await fetchJSONWithOptions(
        `/api/v1/library/books/${encodeURIComponent(String(bookId))}/cover/`,
        {
          method: "DELETE",
          headers: { Accept: "application/json", ...(csrf ? { "X-CSRFToken": csrf } : {}) },
        }
      );
      currentCoverUrl = "";
      onCoverChanged("");
      resetSelection();
      setStatus(statusEl, "Cover cleared.", false);
    } catch (error) {
      console.error("Failed to clear book cover", { bookId, error });
      setStatus(statusEl, coverMutationError(error, "Cover could not be cleared."), true);
    } finally {
      setBusy(false);
    }
  });

  cancelButton.addEventListener("click", close);
  modal.addEventListener("click", (event) => {
    if (event.target === modal) close();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.hidden) close();
  });

  return {
    setCurrentCoverUrl(url) {
      currentCoverUrl = String(url || "");
      clearButton.disabled = !currentCoverUrl;
    },
  };
}
