import {
  extractApiErrorMessage,
  fetchJSON,
  fetchJSONWithOptions,
  getCsrfToken,
  summarizeFieldErrors,
} from "../api.js";
import { canManageGroupMemberships, canManageUsers } from "../auth.js";
import { $, advancedLibraryGroupsEnabled, loadMeAndInitShell, setGlobalError, visible } from "../layout.js";
import { renderUserIdentity } from "../ui/identity.js";
import { setStatus } from "../ui/status.js";
import {
  initUserMembershipsManager,
  loadAllGroups,
  refreshAddGroupOptions,
  renderGroupsReadOnly,
  renderMembershipControls,
} from "./memberships.js";
import { syncUserEditBreadcrumb } from "./navigation.js";
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
  const membershipsResults = $("#user-memberships-results");
  const addForm = $("#user-memberships-add-form");
  const addGroupSelect = $("#user-memberships-add-group");
  const addRoleSelect = $("#user-memberships-add-role");
  const addSubmitBtn = $("#user-memberships-add-submit");
  const addStatus = $("#user-memberships-add-status");
  const groupUiEnabled =
    advancedLibraryGroupsEnabled() &&
    !!groupsEl &&
    !!membershipsCard &&
    !!membershipsResults &&
    !!addForm &&
    !!addGroupSelect &&
    !!addRoleSelect &&
    !!addSubmitBtn &&
    !!addStatus;

  if (
    !root ||
    !notAllowedEl ||
    !statusEl ||
    !cardEl ||
    !form ||
    !usernameEl ||
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
    !resetCopy
  ) {
    return;
  }

  const profileId = root.dataset ? root.dataset.profileId : "";
  if (!profileId) {
    setStatus(statusEl, "Missing profile id.", true);
    return;
  }
  syncUserEditBreadcrumb(null);

  const allowed = canManageUsers(me);
  const canManageMemberships = groupUiEnabled && canManageGroupMemberships(me);
  let original = null;
  let allGroups = null;
  let canResetPassword = false;

  visible(notAllowedEl, !allowed);
  visible(cardEl, allowed);
  visible(membershipsCard, allowed && canManageMemberships);

  function setFormEnabled(on, message) {
    const disabled = !on;
    emailInput.disabled = disabled;
    firstInput.disabled = disabled;
    lastInput.disabled = disabled;
    roleSelect.disabled = disabled;
    activeSelect.disabled = disabled;
    mustChangeInput.disabled = disabled;
    submitBtn.disabled = disabled;
    if (message) setStatus(saveStatus, message, true);
  }

  function applyRoleOptions() {
    const canSetManager = !!(me && me.is_owner);
    const mgrOpt = roleSelect.querySelector('option[value="manager"]');
    if (mgrOpt) mgrOpt.disabled = !canSetManager;
    if (!canSetManager && roleSelect.value === "manager") {
      roleSelect.value = "reader";
    }
  }

  function applyUserPayload(payload) {
    original = payload;
    syncUserEditBreadcrumb(payload);
    usernameEl.replaceChildren(renderUserIdentity(payload));
    if (groupUiEnabled) groupsEl.innerHTML = renderGroupsReadOnly(payload.groups);
    emailInput.value = payload.email || "";
    firstInput.value = payload.first_name || "";
    lastInput.value = payload.last_name || "";
    roleSelect.value = payload.role || "reader";
    activeSelect.value = payload.is_active === false ? "false" : "true";
    mustChangeInput.checked = !!payload.must_change_password;
    applyRoleOptions();
  }

  if (!allowed) {
    setStatus(statusEl, "Not allowed.", true);
    visible(cardEl, false);
    visible(membershipsCard, false);
    return;
  }

  setStatus(statusEl, "Loading...", false);

  try {
    const payload = await fetchJSON(`/api/v1/accounts/users/${encodeURIComponent(String(profileId))}/`);
    applyUserPayload(payload);

    setStatus(statusEl, "", false);
    setStatus(saveStatus, "", false);

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
    setStatus(resetStatus, "", false);

    if (canManageMemberships) {
      allGroups = await loadAllGroups();
      membershipsResults.innerHTML = renderMembershipControls(payload.groups, allGroups, profileId);
      refreshAddGroupOptions({ allGroups, userGroups: payload.groups, addGroupSelect, addSubmitBtn });
      setStatus(addStatus, "", false);
    }
  } catch (e) {
    console.error("Failed to load user", { profileId, e });
    setStatus(statusEl, extractApiErrorMessage(e), true);
    visible(cardEl, false);
    visible(membershipsCard, false);
    return;
  }

  async function refreshUserAndMemberships() {
    const payload = await fetchJSON(`/api/v1/accounts/users/${encodeURIComponent(String(profileId))}/`);
    applyUserPayload(payload);

    if (canManageMemberships) {
      if (!allGroups) allGroups = await loadAllGroups();
      membershipsResults.innerHTML = renderMembershipControls(payload.groups, allGroups, profileId);
      refreshAddGroupOptions({ allGroups, userGroups: payload.groups, addGroupSelect, addSubmitBtn });
    }
    return payload;
  }

  // Wire modules now that refresh callback exists.
  if (groupUiEnabled) {
    initUserMembershipsManager({
      profileId,
      membershipsCard,
      membershipsResults,
      addForm,
      addGroupSelect,
      addRoleSelect,
      addSubmitBtn,
      addStatus,
      canManageMemberships,
      refreshUserAndMemberships,
    });
  }
  initManagedPasswordReset({
    profileId,
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
    setStatus(saveStatus, "Saving...", false);

    if (!original) {
      setStatus(saveStatus, "User not loaded.", true);
      return;
    }

    if (original.is_owner) {
      setStatus(saveStatus, "Owner cannot be edited here.", true);
      return;
    }
    if (!me.is_owner && original.role === "manager") {
      setStatus(saveStatus, "Only Owner can edit Managers.", true);
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
      setStatus(saveStatus, "No changes.", false);
      return;
    }

    if (!me.is_owner && patch.role === "manager") {
      setStatus(saveStatus, "Only Owner can assign manager.", true);
      return;
    }

    try {
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json", "Content-Type": "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;

      const updated = await fetchJSONWithOptions(`/api/v1/accounts/users/${encodeURIComponent(String(profileId))}/`, {
        method: "PATCH",
        headers,
        body: JSON.stringify(patch),
      });

      applyUserPayload(updated);

      setStatus(saveStatus, "Saved.", false);
    } catch (e2) {
      console.error("Failed to save user", { profileId, e2 });
      const msg = extractApiErrorMessage(e2);
      const fieldMsg = summarizeFieldErrors(e2 && e2.body ? e2.body : null);
      setStatus(saveStatus, fieldMsg ? `${msg} (${fieldMsg})` : msg, true);
      setGlobalError(msg);
    }
  });
}
