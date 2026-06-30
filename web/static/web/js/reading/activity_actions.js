export function sessionIsWritable(state) {
  return state.sessionStatus === "active" && state.sessionIsActive === true;
}

export function sessionDisplayLabel(state) {
  const name = state && state.sessionName ? String(state.sessionName).trim() : "";
  if (name) return name;
  const id = state && state.sessionId ? String(state.sessionId).trim() : "";
  return id ? `Unnamed session \u00b7 ${id.slice(-8)}` : "Unnamed session";
}

export function renderSessionDisplay(sessionDisplayEl, state) {
  const sessionDisplayName = sessionDisplayLabel(state);
  if (!sessionDisplayName) {
    sessionDisplayEl.textContent = "";
    return;
  }
  const suffix = sessionIsWritable(state) ? "" : ` (${state.sessionStatus || "closed"})`;
  sessionDisplayEl.textContent = `Session: "${sessionDisplayName}"${suffix}`;
}

export function bindSessionControls({
  elements,
  state,
  visible,
  patchSessionName,
  closeSessionById,
  extractApiErrorMessage,
  summarizeFieldErrors,
  onSessionChanged,
}) {
  const {
    sessionDisplayEl,
    sessionEditBtn,
    sessionEditFormEl,
    sessionNameEl,
    sessionSaveBtn,
    sessionSaveStatusEl,
    sessionCancelBtn,
    sessionCloseBtn,
    sessionCloseStatusEl,
  } = elements;

  function enterEditMode() {
    if (!state.sessionId) return;
    sessionSaveStatusEl.textContent = "";
    sessionNameEl.value = state.sessionName;
    visible(sessionEditBtn, false);
    visible(sessionEditFormEl, true);
    sessionNameEl.focus();
    sessionNameEl.select();
    updateSaveButtonState();
  }

  function exitEditMode() {
    visible(sessionEditFormEl, false);
    visible(sessionEditBtn, !!state.sessionId && state.canEditSessionMetadata);
    sessionSaveStatusEl.textContent = "";
    sessionNameEl.value = state.sessionName;
    updateSaveButtonState();
  }

  function updateSaveButtonState() {
    if (!state.sessionId) {
      sessionSaveBtn.disabled = true;
      return;
    }
    const current = (sessionNameEl.value || "").trim();
    const original = (state.sessionName || "").trim();
    sessionSaveBtn.disabled = current === original;
  }

  sessionNameEl.addEventListener("input", () => {
    sessionSaveStatusEl.textContent = "";
    updateSaveButtonState();
  });

  sessionEditBtn.addEventListener("click", () => enterEditMode());
  sessionCancelBtn.addEventListener("click", () => exitEditMode());

  // Initial UI: display mode when a session exists.
  visible(sessionEditBtn, !!state.sessionId && state.canEditSessionMetadata);
  visible(sessionEditFormEl, false);
  visible(sessionCloseBtn, !!state.sessionId && sessionIsWritable(state));
  sessionCloseStatusEl.textContent = "";

  sessionSaveBtn.addEventListener("click", async () => {
    if (!state.sessionId) return;
    const desired = (sessionNameEl.value || "").trim();

    sessionSaveBtn.disabled = true;
    sessionSaveStatusEl.textContent = "Saving...";
    try {
      const updated = await patchSessionName(state.sessionId, desired);
      state.sessionName = updated && typeof updated.name === "string" ? updated.name : desired;
      sessionNameEl.value = state.sessionName;
      renderSessionDisplay(sessionDisplayEl, state);
      if (typeof onSessionChanged === "function") onSessionChanged(state);
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
    if (!state.sessionId || !sessionIsWritable(state)) return;
    const message = (state.sessionName || "").trim()
      ? "Close this reading session? Closed sessions cannot be edited."
      : "This session has no name. Closed sessions cannot be renamed later. Close anyway?";
    if (!window.confirm(message)) return;

    sessionCloseBtn.disabled = true;
    sessionCloseStatusEl.textContent = "Closing...";
    try {
      const closed = await closeSessionById(state.sessionId);
      state.sessionStatus = closed && typeof closed.status === "string" ? closed.status : "completed";
      state.sessionIsActive = !!(closed && closed.is_active);
      state.sessionName = closed && typeof closed.name === "string" ? closed.name : state.sessionName;
      sessionNameEl.value = state.sessionName;
      state.canEditSessionMetadata = false;
      renderSessionDisplay(sessionDisplayEl, state);
      if (typeof onSessionChanged === "function") onSessionChanged(state);
      visible(sessionEditBtn, false);
      visible(sessionEditFormEl, false);
      visible(sessionCloseBtn, false);
      sessionCloseStatusEl.textContent = "Session closed.";
    } catch (eClose) {
      sessionCloseStatusEl.textContent = extractApiErrorMessage(eClose);
      sessionCloseBtn.disabled = false;
    }
  });
}
