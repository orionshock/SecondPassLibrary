export function syncApplyState(resultsEl, applyControlsEl) {
  resultsEl.querySelectorAll(".import-book-select").forEach((bookBox) => {
    const boxes = [...resultsEl.querySelectorAll(`.import-session-select[data-book-index="${bookBox.dataset.bookIndex}"]:not(:disabled)`)];
    const selected = boxes.filter((box) => box.checked).length;
    bookBox.checked = boxes.length > 0 && selected === boxes.length;
    bookBox.indeterminate = selected > 0 && selected < boxes.length;
  });
  const anySelected = Boolean(resultsEl.querySelector(".import-session-select:checked:not(:disabled)"));
  const applyBtn = applyControlsEl.querySelector("#reading-import-apply-submit");
  if (applyBtn) applyBtn.disabled = !anySelected;
}

export function buildSelection(preview, resultsEl) {
  const books = [];
  (preview.books || []).forEach((book, bookIndex) => {
    const sessions = [];
    resultsEl.querySelectorAll(`.import-session-select[data-book-index="${bookIndex}"]:checked:not(:disabled)`).forEach((box) => {
      const row = box.closest(".import-session");
      sessions.push({
        export_session_id: box.dataset.sessionId || "",
        selected: true,
        name: row.querySelector(".import-session-name")?.value || "",
        notes: row.querySelector(".import-session-notes")?.value || "",
      });
    });
    if (sessions.length) {
      books.push({
        source: book.source || "",
        file_hash: book.file_hash || "",
        title: book.title || "",
        sessions,
      });
    }
  });
  return { books };
}

export function bindSelectionControls({ resultsEl, applyControlsEl }) {
  resultsEl.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLInputElement)) return;
    if (target.classList.contains("import-book-select")) {
      resultsEl.querySelectorAll(`.import-session-select[data-book-index="${target.dataset.bookIndex}"]:not(:disabled)`).forEach((box) => {
        box.checked = target.checked;
      });
    }
    syncApplyState(resultsEl, applyControlsEl);
  });
}

export function handleSelectAllNoneClick({ target, resultsEl, applyControlsEl }) {
  if (target.id !== "reading-import-select-all" && target.id !== "reading-import-select-none" && target.id !== "reading-import-select-all-top" && target.id !== "reading-import-select-none-top") {
    return false;
  }
  const checked = target.id === "reading-import-select-all" || target.id === "reading-import-select-all-top";
  resultsEl.querySelectorAll(".import-session-select:not(:disabled)").forEach((box) => {
    box.checked = checked;
  });
  syncApplyState(resultsEl, applyControlsEl);
  return true;
}
