import {
  extractApiErrorMessage,
  fetchJSONWithOptions,
  getCsrfToken,
  summarizeFieldErrors,
} from "../api.js";
import { $, loadMeAndInitShell, setGlobalError, visible } from "../layout.js";
import { setElStatus } from "./shared.js";

export async function initUserNew() {
  const me = await loadMeAndInitShell();
  setGlobalError("");

  const notAllowedEl = $("#user-new-not-allowed");
  const statusEl = $("#user-new-status");
  const formCard = $("#user-new-form-card");
  const form = $("#user-new-form");
  const usernameInput = $("#user-new-username");
  const emailInput = $("#user-new-email");
  const firstInput = $("#user-new-first");
  const lastInput = $("#user-new-last");
  const roleSelect = $("#user-new-role");
  const activeInput = $("#user-new-active");
  const submitBtn = $("#user-new-submit");
  const submitStatus = $("#user-new-submit-status");

  const successCard = $("#user-new-success");
  const createdUsername = $("#user-new-created-username");
  const createdPassword = $("#user-new-created-password");

  if (
    !notAllowedEl ||
    !statusEl ||
    !formCard ||
    !form ||
    !usernameInput ||
    !emailInput ||
    !firstInput ||
    !lastInput ||
    !roleSelect ||
    !activeInput ||
    !submitBtn ||
    !submitStatus ||
    !successCard ||
    !createdUsername ||
    !createdPassword
  ) {
    return;
  }

  const caps = me && me.capabilities ? me.capabilities : {};
  const allowed = !!caps.can_manage_users;

  visible(notAllowedEl, !allowed);
  visible(formCard, allowed);

  if (!allowed) {
    statusEl.textContent = "Not allowed.";
    statusEl.classList.add("error");
    return;
  }

  statusEl.textContent = "";
  statusEl.classList.remove("error");

  const canCreateManager = !!(me && me.is_owner);
  const mgrOpt = roleSelect.querySelector('option[value="manager"]');
  if (mgrOpt) mgrOpt.disabled = !canCreateManager;
  if (!canCreateManager && roleSelect.value === "manager") {
    roleSelect.value = "reader";
  }

  function setSubmitStatus(text, isError) {
    setElStatus(submitStatus, text, isError);
  }

  function setFormEnabled(on) {
    const disabled = !on;
    usernameInput.disabled = disabled;
    emailInput.disabled = disabled;
    firstInput.disabled = disabled;
    lastInput.disabled = disabled;
    roleSelect.disabled = disabled;
    activeInput.disabled = disabled;
    submitBtn.disabled = disabled;
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    setGlobalError("");
    setSubmitStatus("Creatingâ€¦", false);
    setFormEnabled(false);

    const payload = {
      username: (usernameInput.value || "").trim(),
      email: (emailInput.value || "").trim(),
      first_name: (firstInput.value || "").trim(),
      last_name: (lastInput.value || "").trim(),
      role: roleSelect.value || "reader",
      is_active: !!activeInput.checked,
    };

    if (!payload.username) {
      setSubmitStatus("Username is required.", true);
      setFormEnabled(true);
      return;
    }

    if (!canCreateManager && payload.role === "manager") {
      setSubmitStatus("Only Owner can create Managers.", true);
      setFormEnabled(true);
      return;
    }

    try {
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json", "Content-Type": "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;

      const created = await fetchJSONWithOptions("/api/v1/accounts/users/", {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });

      const u = created && created.user ? created.user : null;
      const pw = created && created.temporary_password ? String(created.temporary_password) : "";

      if (!u || !pw) {
        throw new Error("Unexpected response from server.");
      }

      createdUsername.textContent = u.username || payload.username;
      createdPassword.textContent = pw;

      visible(formCard, false);
      visible(successCard, true);
      setSubmitStatus("", false);
    } catch (e2) {
      console.error("Failed to create user", { e2 });
      const msg = extractApiErrorMessage(e2);
      const fieldMsg = summarizeFieldErrors(e2 && e2.body ? e2.body : null);
      setSubmitStatus(fieldMsg ? `${msg} (${fieldMsg})` : msg, true);
      setGlobalError(msg);
      setFormEnabled(true);
    }
  });
}

