import { $, loadMeAndInitShell } from "./layout.js";

export async function initReadingBookSessions() {
  await loadMeAndInitShell();

  const root = $("#reading-sessions");
  const button = $("#reading-sessions-export-selected");
  const boxes = Array.from(document.querySelectorAll(".reading-session-select"));
  if (!root || !button || !boxes.length) return;

  function selectedIds() {
    return boxes
      .filter((box) => box.checked)
      .map((box) => String(box.value || "").trim())
      .filter(Boolean);
  }

  function updateButton() {
    button.disabled = selectedIds().length === 0;
  }

  boxes.forEach((box) => box.addEventListener("change", updateButton));
  button.addEventListener("click", () => {
    const bookId = String(root.dataset.bookId || "").trim();
    const ids = selectedIds();
    if (!bookId || !ids.length) return;

    const params = new URLSearchParams();
    ids.forEach((id) => params.append("session", id));
    window.location.href = `/api/v1/reading/export/books/${encodeURIComponent(bookId)}/?${params.toString()}`;
  });

  updateButton();
}
