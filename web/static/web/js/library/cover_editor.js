import {
  fetchJSONWithOptions,
  getCsrfToken,
  summarizeFieldErrors,
} from "../api.js";
import { $, setText, visible } from "../layout.js";
import { mountCovers } from "../ui/covers.js";
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
  const root = $("#book-edit-cover-editor");
  const currentCover = $("#book-edit-cover-current");
  const form = $("#book-edit-cover-form");
  const fileInput = $("#book-edit-cover-file");
  const selection = $("#book-edit-cover-selection");
  const previewWrap = $("#book-edit-cover-preview-wrap");
  const preview = $("#book-edit-cover-preview");
  const statusEl = $("#book-edit-cover-status");
  const submitButton = $("#book-edit-cover-submit");
  const clearButton = $("#book-edit-cover-clear");
  const resetButton = $("#book-edit-cover-reset");
  if (
    !root ||
    !currentCover ||
    !form ||
    !fileInput ||
    !selection ||
    !previewWrap ||
    !preview ||
    !statusEl ||
    !submitButton ||
    !clearButton ||
    !resetButton
  )
    return null;

  let currentCoverUrl = "";
  let currentTitle = "";
  let previewUrl = "";

  function renderCurrentCover() {
    currentCover.dataset.coverUrl = currentCoverUrl;
    currentCover.dataset.coverTitle = currentTitle;
    currentCover.dataset.coverMounted = "0";
    mountCovers(currentCover.parentNode);
    visible(clearButton, !!currentCoverUrl);
  }

  function discardPreview() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = "";
    preview.removeAttribute("src");
    visible(previewWrap, false);
  }

  function resetSelection({ clearStatus = true } = {}) {
    discardPreview();
    fileInput.value = "";
    setText(selection, "No image selected.");
    if (clearStatus) setStatus(statusEl, "", false);
  }

  function setBusy(busy) {
    fileInput.disabled = busy;
    submitButton.disabled = busy;
    clearButton.disabled = busy;
    resetButton.disabled = busy;
  }

  fileInput.addEventListener("change", () => {
    discardPreview();
    setStatus(statusEl, "", false);
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
      currentTitle = book && book.title ? String(book.title) : currentTitle;
      renderCurrentCover();
      onCoverChanged(currentCoverUrl, book);
      resetSelection({ clearStatus: false });
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
      const book = await fetchJSONWithOptions(
        `/api/v1/library/books/${encodeURIComponent(String(bookId))}/cover/`,
        {
          method: "DELETE",
          headers: { Accept: "application/json", ...(csrf ? { "X-CSRFToken": csrf } : {}) },
        }
      );
      currentCoverUrl = "";
      renderCurrentCover();
      onCoverChanged("", book);
      resetSelection({ clearStatus: false });
      setStatus(statusEl, "Cover cleared.", false);
    } catch (error) {
      console.error("Failed to clear book cover", { bookId, error });
      setStatus(statusEl, coverMutationError(error, "Cover could not be cleared."), true);
    } finally {
      setBusy(false);
    }
  });

  resetButton.addEventListener("click", () => resetSelection());

  return {
    setCurrentCover({ url, title }) {
      currentCoverUrl = String(url || "");
      currentTitle = String(title || "");
      renderCurrentCover();
    },
  };
}
