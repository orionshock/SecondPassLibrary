import { loadMeAndInitShell } from "../layout.js";
import { getCsrfToken } from "../api.js";

function bookRows() {
  return [...document.querySelectorAll("[data-export-book-row]")];
}

function sessionBoxes(row) {
  return [...row.querySelectorAll(".export-session-select")];
}

function checkedSessionBoxes(row) {
  return sessionBoxes(row).filter((box) => box.checked);
}

function updateBookState(row) {
  const bookBox = row.querySelector(".export-book-select");
  if (!bookBox) return;
  const boxes = sessionBoxes(row);
  const checked = checkedSessionBoxes(row).length;
  bookBox.checked = boxes.length > 0 && checked === boxes.length;
  bookBox.indeterminate = checked > 0 && checked < boxes.length;
}

function selectedBooks() {
  return bookRows().filter((row) => checkedSessionBoxes(row).length > 0);
}

function selectedExportBody() {
  const books = selectedBooks().map((row) => {
    const checked = checkedSessionBoxes(row);
    const all = sessionBoxes(row);
    const sessions = checked.length === all.length
      ? "all"
      : checked.map((box) => box.dataset.sessionId || "").filter(Boolean);
    return { book_id: row.dataset.bookId || "", sessions };
  }).filter((book) => book.book_id && (book.sessions === "all" || book.sessions.length));
  return { books };
}

function selectedSummary() {
  const rows = selectedBooks();
  if (!rows.length) return "No selection";
  const sessionCount = rows.reduce((total, row) => total + checkedSessionBoxes(row).length, 0);
  const sessionNoun = sessionCount === 1 ? "session" : "sessions";
  const bookNoun = rows.length === 1 ? "book" : "books";
  return `${sessionCount} ${sessionNoun} selected from ${rows.length} ${bookNoun}`;
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

function selectAll() {
  bookRows().forEach((row) => {
    const bookBox = row.querySelector(".export-book-select");
    if (bookBox) {
      bookBox.checked = true;
      bookBox.indeterminate = false;
    }
    sessionBoxes(row).forEach((box) => {
      box.checked = true;
    });
  });
}

function updateSelectedAction(message = "") {
  bookRows().forEach(updateBookState);
  const button = document.getElementById("reading-export-selected");
  const status = document.getElementById("reading-export-selection-status");
  const summary = document.getElementById("reading-export-selection-summary");
  const clearButton = document.getElementById("reading-export-clear");
  const hasSelection = selectedBooks().length > 0;
  if (button) {
    button.disabled = !hasSelection;
  }
  if (clearButton) clearButton.disabled = !hasSelection;
  if (summary) summary.textContent = selectedSummary();
  if (status) {
    status.textContent = hasSelection
      ? message || "Ready to export selected marginalia."
      : "Select books or sessions.";
  }
}

function setSelectionStatus(message) {
  const status = document.getElementById("reading-export-selection-status");
  if (status) status.textContent = message;
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

function isInteractiveElement(target) {
  return Boolean(target.closest("a, button, input, select, textarea, label"));
}

function toggleBookSelection(row) {
  const bookBox = row.querySelector(".export-book-select");
  if (!(bookBox instanceof HTMLInputElement)) return;
  bookBox.checked = !bookBox.checked;
  sessionBoxes(row).forEach((box) => {
    box.checked = bookBox.checked;
  });
  updateSelectedAction();
}

async function exportSelected(button) {
  const body = selectedExportBody();
  if (!body.books.length || button.disabled) return;
  button.disabled = true;
  setSelectionStatus("Preparing selected export.");
  try {
    const response = await fetch("/api/v1/reading/export/", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken() || "",
      },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error(`Export failed (${response.status}).`);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "second-pass-marginalia.json";
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    updateSelectedAction("Selected export downloaded.");
  } catch (error) {
    console.error(error);
    updateSelectedAction("Selected export failed.");
  }
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
      sessionBoxes(row).forEach((box) => {
        box.checked = target.checked;
      });
      updateSelectedAction();
      return;
    }

    if (target.classList.contains("export-session-select")) {
      const row = target.closest("[data-export-book-row]");
      if (!row) return;
      updateSelectedAction();
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
      exportSelected(target);
      return;
    }

    if (target.id === "reading-export-clear" && target instanceof HTMLButtonElement) {
      clearSelection();
      updateSelectedAction();
      return;
    }

    if (target.id === "reading-export-select-all" && target instanceof HTMLButtonElement) {
      selectAll();
      updateSelectedAction();
      return;
    }

    const row = target.closest("[data-export-book-row]");
    if (row && !target.closest(".export-session-list") && !isInteractiveElement(target)) {
      toggleBookSelection(row);
    }
  });

  updateSelectedAction();
}
