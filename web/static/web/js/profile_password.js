import { fetchJSONWithOptions, getCsrfToken, extractApiErrorMessage } from "./api.js";
import { $, loadMeAndInitShell, setGlobalError } from "./layout.js";

export async function initProfilePassword() {
  const me = await loadMeAndInitShell();
  const noteEl = $("#profile-password-note");
  if (noteEl) {
    if (me && me.must_change_password) {
      noteEl.textContent = "You must change your password before continuing.";
      noteEl.classList.add("error");
    } else {
      noteEl.textContent = "";
      noteEl.classList.remove("error");
    }
  }

  const form = $("#profile-password-form");
  const currentInput = $("#profile-password-current");
  const newInput = $("#profile-password-new");
  const confirmInput = $("#profile-password-confirm");
  const submitBtn = $("#profile-password-submit");
  const statusEl = $("#profile-password-status");

  if (!form || !currentInput || !newInput || !confirmInput || !submitBtn || !statusEl) return;

  function setStatus(text, isError) {
    statusEl.textContent = text || "";
    statusEl.classList.toggle("error", !!isError);
  }

  function setEnabled(on) {
    const disabled = !on;
    currentInput.disabled = disabled;
    newInput.disabled = disabled;
    confirmInput.disabled = disabled;
    submitBtn.disabled = disabled;
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    setGlobalError("");

    const current_password = String(currentInput.value || "");
    const new_password = String(newInput.value || "");
    const confirm = String(confirmInput.value || "");

    if (!current_password) {
      setStatus("Current password is required.", true);
      return;
    }
    if (!new_password) {
      setStatus("New password is required.", true);
      return;
    }
    if (new_password !== confirm) {
      setStatus("New passwords do not match.", true);
      return;
    }

    setStatus("Saving…", false);
    setEnabled(false);

    try {
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json", "Content-Type": "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;

      await fetchJSONWithOptions("/api/v1/accounts/me/change-password/", {
        method: "POST",
        headers,
        body: JSON.stringify({ current_password, new_password, confirm_password: confirm }),
      });

      currentInput.value = "";
      newInput.value = "";
      confirmInput.value = "";

      setStatus("Saved. Redirecting", false);
      if (noteEl) {
        noteEl.textContent = "";
        noteEl.classList.remove("error");
      }

      window.setTimeout(() => {
        window.location.assign("/profile/");
      }, 750);
    } catch (e2) {
      console.error("Failed to change password", e2);
      const msg = extractApiErrorMessage(e2);
      setStatus(msg, true);
      setGlobalError(msg);
    } finally {
      setEnabled(true);
    }
  });
}
