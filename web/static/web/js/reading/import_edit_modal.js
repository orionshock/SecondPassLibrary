export function bindImportEditModal({ resultsEl, modal, modalForm, modalName, modalNotes, modalCancel }) {
  let editingSession = null;

  resultsEl.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement) || !target.classList.contains("import-session-edit")) return;
    editingSession = target.closest(".import-session");
    if (!editingSession) return;
    modalName.value = editingSession.querySelector(".import-session-name")?.value || "";
    modalNotes.value = editingSession.querySelector(".import-session-notes")?.value || "";
    modal.hidden = false;
    modalName.focus();
  });

  modalForm.addEventListener("submit", (event) => {
    event.preventDefault();
    if (editingSession) {
      const nameInput = editingSession.querySelector(".import-session-name");
      const notesInput = editingSession.querySelector(".import-session-notes");
      if (nameInput) nameInput.value = modalName.value;
      if (notesInput) notesInput.value = modalNotes.value;
    }
    modal.hidden = true;
    editingSession = null;
  });

  modalCancel.addEventListener("click", () => {
    modal.hidden = true;
    editingSession = null;
  });
}
