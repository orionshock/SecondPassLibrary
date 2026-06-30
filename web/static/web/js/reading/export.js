import { loadMeAndInitShell } from "../layout.js";

function bookRows() {
  return [...document.querySelectorAll("[data-export-book-row]")];
}

function sessionBoxes(row) {
  return [...row.querySelectorAll(".export-session-select")];
}

function checkedSessionBoxes(row) {
  return sessionBoxes(row).filter((box) => box.checked);
}

function clearOtherBooks(activeBookId) {
  let cleared = false;
  bookRows().forEach((row) => {
    if (row.dataset.bookId === activeBookId) return;
    const hadSelection = checkedSessionBoxes(row).length > 0;
    const bookBox = row.querySelector(".export-book-select");
    if (bookBox) {
      bookBox.checked = false;
      bookBox.indeterminate = false;
    }
    sessionBoxes(row).forEach((box) => {
      box.checked = false;
    });
    cleared = cleared || hadSelection;
  });
  return cleared;
}

function updateBookState(row) {
  const bookBox = row.querySelector(".export-book-select");
  if (!bookBox) return;
  const boxes = sessionBoxes(row);
  const checked = checkedSessionBoxes(row).length;
  bookBox.checked = boxes.length > 0 && checked === boxes.length;
  bookBox.indeterminate = checked > 0 && checked < boxes.length;
}

function selectedRow() {
  return bookRows().find((row) => checkedSessionBoxes(row).length > 0) || null;
}

function selectedExportUrl(row) {
  const bookId = row && row.dataset ? row.dataset.bookId : "";
  if (!bookId) return "";
  const checked = checkedSessionBoxes(row);
  const all = sessionBoxes(row);
  const base = `/api/v1/reading/export/books/${encodeURIComponent(bookId)}/`;
  if (!checked.length) return "";
  if (checked.length === all.length) return base;
  const params = new URLSearchParams();
  checked.forEach((box) => params.append("session", box.dataset.sessionId || ""));
  return `${base}?${params.toString()}`;
}

function selectedSummary(row) {
  if (!row) return "No selection";
  const count = checkedSessionBoxes(row).length;
  if (!count) return "No selection";
  const noun = count === 1 ? "session" : "sessions";
  return `${count} ${noun} selected from 1 book`;
}

function clearSelection() {
  bookRows().forEach((row) => {
    const bookBox = row.querySelector(".export-book-select");
    if (bookBox) {
      bookBox.checked = false;
      bookBox.indeterminate = false;
    }
    sessionBoxes(row).forEach((box) => {
      box.checked = false;
    });
  });
}

function updateSelectedAction(message = "") {
  bookRows().forEach(updateBookState);
  const button = document.getElementById("reading-export-selected");
  const status = document.getElementById("reading-export-selection-status");
  const summary = document.getElementById("reading-export-selection-summary");
  const clearButton = document.getElementById("reading-export-clear");
  const row = selectedRow();
  const url = selectedExportUrl(row);
  if (button) {
    button.disabled = !url;
    button.dataset.exportUrl = url;
  }
  if (clearButton) clearButton.disabled = !url;
  if (summary) summary.textContent = selectedSummary(row);
  if (status) {
    status.textContent = url
      ? message || "Ready to export selected marginalia."
      : "Select one book or session.";
  }
}

function toggleSessions(button) {
  const row = button.closest("[data-export-book-row]");
  const targetId = button.getAttribute("aria-controls") || "";
  const target = targetId ? document.getElementById(targetId) : null;
  if (!row || !target) return;
  const expanded = button.getAttribute("aria-expanded") === "true";
  button.setAttribute("aria-expanded", expanded ? "false" : "true");
  button.textContent = expanded ? "Show sessions" : "Hide sessions";
  target.hidden = expanded;
}

export async function initReadingExport() {
  await loadMeAndInitShell();
  const root = document.getElementById("reading-export-workflow");
  if (!root) return;

  root.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLInputElement)) return;

    if (target.classList.contains("export-book-select")) {
      const row = target.closest("[data-export-book-row]");
      if (!row) return;
      const cleared = target.checked ? clearOtherBooks(row.dataset.bookId || "") : false;
      sessionBoxes(row).forEach((box) => {
        box.checked = target.checked;
      });
      updateSelectedAction(cleared ? "Export selected currently supports one book at a time." : "");
      return;
    }

    if (target.classList.contains("export-session-select")) {
      const row = target.closest("[data-export-book-row]");
      if (!row) return;
      const cleared = target.checked ? clearOtherBooks(row.dataset.bookId || "") : false;
      updateSelectedAction(cleared ? "Export selected currently supports one book at a time." : "");
    }
  });

  root.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;

    const toggle = target.closest(".export-sessions-toggle");
    if (toggle instanceof HTMLButtonElement) {
      toggleSessions(toggle);
      return;
    }

    if (target.id === "reading-export-selected" && target instanceof HTMLButtonElement) {
      const url = target.dataset.exportUrl || "";
      if (url && !target.disabled) window.location.assign(url);
      return;
    }

    if (target.id === "reading-export-clear" && target instanceof HTMLButtonElement) {
      clearSelection();
      updateSelectedAction();
    }
  });

  updateSelectedAction();
}
