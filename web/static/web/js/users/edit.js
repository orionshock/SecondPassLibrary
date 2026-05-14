import {
  extractApiErrorMessage,
  fetchJSON,
  fetchJSONWithOptions,
  getCsrfToken,
  summarizeFieldErrors,
} from "../api.js";
import { $, loadMeAndInitShell, setGlobalError, visible } from "../layout.js";
import { setElStatus } from "./shared.js";
import {
  initUserMembershipsManager,
  loadAllGroups,
  refreshAddGroupOptions,
  renderGroupsReadOnly,
  renderMembershipControls,
} from "./memberships.js";
import { initManagedPasswordReset } from "./password_reset.js";

export async function initUserEdit() {
  const me = await loadMeAndInitShell();
  setGlobalError("");

  const root = $("#user-edit");
  const notAllowedEl = $("#user-edit-not-allowed");
  const statusEl = $("#user-edit-status");
  const cardEl = $("#user-edit-card");
  const form = $("#user-edit-form");
  const usernameEl = $("#user-edit-username");
  const groupsEl = $("#user-edit-groups");
  const emailInput = $("#user-edit-email");
  const firstInput = $("#user-edit-first");
  const lastInput = $("#user-edit-last");
  const roleSelect = $("#user-edit-role");
  const activeSelect = $("#user-edit-active");
  const mustChangeInput = $("#user-edit-must-change");
  const submitBtn = $("#user-edit-submit");
  const saveStatus = $("#user-edit-save-status");

  const passwordCard = $("#user-password-card");
  const resetBtn = $("#user-reset-password-btn");
  const resetStatus = $("#user-reset-password-status");
  const resetResult = $("#user-reset-password-result");
  const resetCopy = $("#user-reset-password-copy");

  const membershipsCard = $("#user-memberships-card");
  const membershipsStatus = $("#user-memberships-status");
  const membershipsResults = $("#user-memberships-results");
  const addForm = $("#user-memberships-add-form");
  const addGroupSelect = $("#user-memberships-add-group");
  const addRoleSelect = $("#user-memberships-add-role");
  const addSubmitBtn = $("#user-memberships-add-submit");
  const addStatus = $("#user-memberships-add-status");

  if (
    !root ||
    !notAllowedEl ||
    !statusEl ||
    !cardEl ||
    !form ||
    !usernameEl ||
    !groupsEl ||
    !emailInput ||
    !firstInput ||
    !lastInput ||
    !roleSelect ||
    !activeSelect ||
    !mustChangeInput ||
    !submitBtn ||
    !saveStatus ||
    !passwordCard ||
    !resetBtn ||
    !resetStatus ||
    !resetResult ||
    !resetCopy ||
    !membershipsCard ||
    !membershipsStatus ||
    !membershipsResults ||
    !addForm ||
    !addGroupSelect ||
    !addRoleSelect ||
    !addSubmitBtn ||
    !addStatus
  ) {
    return;
  }

  const userId = root.dataset ? root.dataset.userId : "";
  if (!userId) {
    statusEl.textContent = "Missing user id.";
    statusEl.classList.add("error");
    return;
  }

  const caps = me && me.capabilities ? me.capabilities : {};
  const allowed = !!caps.can_manage_users;
  const canManageMemberships = !!caps.can_manage_group_memberships;

  visible(notAllowedEl, !allowed);
  visible(cardEl, allowed);
  visible(membershipsCard, allowed && canManageMemberships);

  function setStatus(text, isError) {
    setElStatus(statusEl, text, isError);
  }

  function setSaveStatus(text, isError) {
    setElStatus(saveStatus, text, isError);
  }

  function setResetStatus(text, isError) {
    setElStatus(resetStatus, text, isError);
  }

  function setMembershipsStatus(text, isError) {
    setElStatus(membershipsStatus, text, isError);
  }

  function setAddStatus(text, isError) {
    setElStatus(addStatus, text, isError);
  }

  function setFormEnabled(on, message) {
    const disabled = !on;
    emailInput.disabled = disabled;
    firstInput.disabled = disabled;
    lastInput.disabled = disabled;
    roleSelect.disabled = disabled;
    activeSelect.disabled = disabled;
    mustChangeInput.disabled = disabled;
    submitBtn.disabled = disabled;
    if (message) setSaveStatus(message, true);
  }

  function applyRoleOptions() {
    const canSetManager = !!(me && me.is_owner);
    const mgrOpt = roleSelect.querySelector('option[value="manager"]');
    if (mgrOpt) mgrOpt.disabled = !canSetManager;
    if (!canSetManager && roleSelect.value === "manager") {
      roleSelect.value = "reader";
    }
  }

  if (!allowed) {
    setStatus("Not allowed.", true);
    visible(cardEl, false);
    visible(membershipsCard, false);
    return;
  }

  setStatus("Loadingâ€¦", false);
  let original = null;
  let allGroups = null;
  let canResetPassword = false;

  try {
    const payload = await fetchJSON(`/api/v1/accounts/users/${encodeURIComponent(String(userId))}/`);
    original = payload;
    usernameEl.textContent = payload.username || "";
    groupsEl.innerHTML = renderGroupsReadOnly(payload.groups);
    emailInput.value = payload.email || "";
    firstInput.value = payload.first_name || "";
    lastInput.value = payload.last_name || "";
    roleSelect.value = payload.role || "reader";
    activeSelect.value = payload.is_active === false ? "false" : "true";
    mustChangeInput.checked = !!payload.must_change_password;

    applyRoleOptions();

    setStatus("", false);
    setSaveStatus("", false);

    if (payload.is_owner) {
      setFormEnabled(false, "Owner cannot be edited here.");
    } else if (!me.is_owner && payload.role === "manager") {
      setFormEnabled(false, "Only Owner can edit Managers.");
    } else {
      setFormEnabled(true, "");
    }

    // Password reset visibility rules (also enforced server-side).
    canResetPassword = false;
    if (me && payload) {
      const isSelf = String(me.username || "") === String(payload.username || "");
      const actorIsManager = !me.is_owner && String(me.role || "") === "manager";
      const actorIsOwner = !!me.is_owner;

      if (!isSelf) {
        if (actorIsOwner) {
          canResetPassword = true;
        } else if (actorIsManager) {
          canResetPassword = !payload.is_owner && String(payload.role || "") !== "manager";
        }
      }
    }
    visible(passwordCard, canResetPassword);
    visible(resetResult, false);
    resetCopy.value = "";
    setResetStatus("", false);

    if (canManageMemberships) {
      setMembershipsStatus("", false);
      membershipsResults.innerHTML = renderMembershipControls(payload.groups);
      allGroups = await loadAllGroups();
      refreshAddGroupOptions({ allGroups, userGroups: payload.groups, addGroupSelect, addSubmitBtn });
      setAddStatus("", false);
    }
  } catch (e) {
    console.error("Failed to load user", { userId, e });
    setStatus(extractApiErrorMessage(e), true);
    visible(cardEl, false);
    visible(membershipsCard, false);
    return;
  }

  async function refreshUserAndMemberships() {
    const payload = await fetchJSON(`/api/v1/accounts/users/${encodeURIComponent(String(userId))}/`);
    original = payload;
    usernameEl.textContent = payload.username || "";
    groupsEl.innerHTML = renderGroupsReadOnly(payload.groups);
    emailInput.value = payload.email || "";
    firstInput.value = payload.first_name || "";
    lastInput.value = payload.last_name || "";
    roleSelect.value = payload.role || "reader";
    activeSelect.value = payload.is_active === false ? "false" : "true";
    mustChangeInput.checked = !!payload.must_change_password;
    applyRoleOptions();

    if (canManageMemberships) {
      membershipsResults.innerHTML = renderMembershipControls(payload.groups);
      if (!allGroups) allGroups = await loadAllGroups();
      refreshAddGroupOptions({ allGroups, userGroups: payload.groups, addGroupSelect, addSubmitBtn });
    }
    return payload;
  }

  // Wire modules now that refresh callback exists.
  initUserMembershipsManager({
    userId,
    membershipsCard,
    membershipsStatus,
    membershipsResults,
    addForm,
    addGroupSelect,
    addRoleSelect,
    addSubmitBtn,
    addStatus,
    canManageMemberships,
    refreshUserAndMemberships,
  });
  initManagedPasswordReset({
    userId,
    canResetPassword,
    resetBtn,
    resetStatus,
    resetResult,
    resetCopy,
    refreshUserAndMemberships,
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    setGlobalError("");
    setSaveStatus("Savingâ€¦", false);

    if (!original) {
      setSaveStatus("User not loaded.", true);
      return;
    }

    if (original.is_owner) {
      setSaveStatus("Owner cannot be edited here.", true);
      return;
    }
    if (!me.is_owner && original.role === "manager") {
      setSaveStatus("Only Owner can edit Managers.", true);
      return;
    }

    const desired = {
      email: emailInput.value || "",
      first_name: firstInput.value || "",
      last_name: lastInput.value || "",
      role: roleSelect.value || "reader",
      is_active: activeSelect.value === "true",
      must_change_password: !!mustChangeInput.checked,
    };

    const patch = {};
    for (const key of Object.keys(desired)) {
      if (String(desired[key]) !== String(original[key])) {
        patch[key] = desired[key];
      }
    }

    if (Object.keys(patch).length === 0) {
      setSaveStatus("No changes.", false);
      return;
    }

    if (!me.is_owner && patch.role === "manager") {
      setSaveStatus("Only Owner can assign manager.", true);
      return;
    }

    try {
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json", "Content-Type": "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;

      const updated = await fetchJSONWithOptions(`/api/v1/accounts/users/${encodeURIComponent(String(userId))}/`, {
        method: "PATCH",
        headers,
        body: JSON.stringify(patch),
      });

      original = updated;
      usernameEl.textContent = updated.username || "";
      groupsEl.innerHTML = renderGroupsReadOnly(updated.groups);
      emailInput.value = updated.email || "";
      firstInput.value = updated.first_name || "";
      lastInput.value = updated.last_name || "";
      roleSelect.value = updated.role || "reader";
      activeSelect.value = updated.is_active === false ? "false" : "true";
      applyRoleOptions();

      setSaveStatus("Saved.", false);
    } catch (e2) {
      console.error("Failed to save user", { userId, e2 });
      const msg = extractApiErrorMessage(e2);
      const fieldMsg = summarizeFieldErrors(e2 && e2.body ? e2.body : null);
      setSaveStatus(fieldMsg ? `${msg} (${fieldMsg})` : msg, true);
      setGlobalError(msg);
    }
  });
}
