import {
  extractApiErrorMessage,
  fetchJSONWithOptions,
  getCsrfToken,
  summarizeFieldErrors,
} from "../api.js";
import { setGlobalError, visible } from "../layout.js";
import { createPagedListController } from "../ui/paged_list.js";
import {
  canManageGroupMemberships,
  loadAllManageableUsers,
  renderMembersManage,
  renderMembersReadOnly,
} from "./shared.js";
import { setStatus } from "../ui/status.js";

export async function initGroupMembershipsTab({
  me,
  groupId,
  isPublicGroup,
  membersNote,
  addMemberForm,
  addMemberUser,
  addMemberRole,
  addMemberStatus,
  membersStatus,
  membersResults,
  membersNext,
  membersPrev,
}) {
  const allowMembershipManage = canManageGroupMemberships(me);
  membersNote.textContent = allowMembershipManage
    ? ""
    : "Membership management is Manager/Owner only. This list is read-only for your account.";

  visible(addMemberForm, allowMembershipManage);
  if (isPublicGroup) {
    membersNote.textContent = allowMembershipManage
      ? "Public is the default/fallback group. Public cannot have curators. Public membership can be removed when another group remains (final removal restores Public)."
      : membersNote.textContent;
    addMemberRole.checked = false;
    addMemberRole.disabled = true;
  }

  function setAddMemberStatus(text, isError) {
    setStatus(addMemberStatus, text, isError);
  }

  const membersCtl = await createPagedListController({
    statusEl: membersStatus,
    resultsEl: membersResults,
    nextBtn: membersNext,
    prevBtn: membersPrev,
    initialUrl: `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/`,
    emptyText: "No members.",
    render: (payload) =>
      allowMembershipManage ? renderMembersManage(payload, { isPublicGroup }) : renderMembersReadOnly(payload),
  });

  if (!allowMembershipManage) return { membersCtl };

  let liveStatusTimer = null;
  function clearLiveStatusLater(rowStatus) {
    if (liveStatusTimer) window.clearTimeout(liveStatusTimer);
    liveStatusTimer = window.setTimeout(() => {
      if (rowStatus) {
        rowStatus.textContent = "";
        rowStatus.classList.remove("error");
      }
    }, 5000);
  }

  try {
    const users = await loadAllManageableUsers();
    addMemberUser.textContent = "";
    for (const u of users) {
      const opt = document.createElement("option");
      opt.value = String(u.profile_id || "");
      opt.textContent = `${u.username} (${u.email || ""})`;
      addMemberUser.appendChild(opt);
    }
  } catch (e) {
    console.error("Failed to load manageable users", e);
    addMemberUser.textContent = "";
    setAddMemberStatus("Error loading user list.", true);
  }

  addMemberForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    setAddMemberStatus("Adding...", false);
    setGlobalError("");

    const profileId = addMemberUser.value;
    if (!profileId) {
      setAddMemberStatus("Choose a user.", true);
      return;
    }

    try {
      const isCurator = !isPublicGroup && !!addMemberRole.checked;
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json", "Content-Type": "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;

      await fetchJSONWithOptions(`/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/`, {
        method: "POST",
        headers,
        body: JSON.stringify({ user_id: String(profileId), is_curator: isCurator }),
      });

      setAddMemberStatus("Added.", false);
      await membersCtl.reloadFirstPage();
    } catch (e2) {
      console.error("Failed to add member", { groupId, e2 });
      const msg = extractApiErrorMessage(e2);
      const fieldMsg = summarizeFieldErrors(e2 && e2.body ? e2.body : null);
      setAddMemberStatus(fieldMsg || msg, true);
      setGlobalError(fieldMsg || msg);
    }
  });

  membersResults.addEventListener("click", async (e) => {
    const source = e.target;
    if (!source || source.nodeType !== 1) return;
    const target = source.closest("[data-action]");
    if (!target || !membersResults.contains(target)) return;
    const action = target.getAttribute("data-action");
    const userId = target.getAttribute("data-user-id");
    if (!action || !userId) return;

    if (action === "member-remove") {
      const row = target.closest(".membership-row");
      const rowStatus = row ? row.querySelector(".membership-row__status") : null;
      function setRowStatus(text, isError) {
        if (!rowStatus) return;
        rowStatus.textContent = text || "";
        rowStatus.classList.toggle("error", !!isError);
      }

      if (!window.confirm("Remove this user from the group?")) return;

      try {
        setRowStatus("Removing...", false);
        setGlobalError("");
        const csrf = getCsrfToken();
        const headers = { Accept: "application/json" };
        if (csrf) headers["X-CSRFToken"] = csrf;

        await fetchJSONWithOptions(
          `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/${encodeURIComponent(
            String(userId)
          )}/`,
          { method: "DELETE", headers }
        );
        setRowStatus("Removed.", false);
        await membersCtl.reloadFirstPage();
      } catch (e2) {
        console.error("Failed to remove member", { groupId, userId, e2 });
        const msg = extractApiErrorMessage(e2);
        setRowStatus(msg, true);
        setStatus(membersStatus, msg, true);
        setGlobalError(msg);
      }
    }
  });

  membersResults.addEventListener("change", async (e) => {
    const source = e.target;
    if (!source || source.nodeType !== 1) return;
    const target = source.closest('input[data-action="member-curator"]');
    if (!target || !membersResults.contains(target)) return;

    const userId = target.getAttribute("data-user-id") || "";
    const row = target.closest(".membership-row");
    const rowStatus = row ? row.querySelector(".membership-row__status") : null;
    const desired = !!target.checked;
    function setRowStatus(text, isError) {
      if (!rowStatus) return;
      rowStatus.textContent = text || "";
      rowStatus.classList.toggle("error", !!isError);
    }

    if (!userId) {
      setRowStatus("Missing user identifier.", true);
      target.checked = !desired;
      return;
    }

    try {
      target.disabled = true;
      setRowStatus("Saving...", false);
      setGlobalError("");

      const csrf = getCsrfToken();
      const headers = { Accept: "application/json", "Content-Type": "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;

      await fetchJSONWithOptions(
        `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/${encodeURIComponent(
          String(userId)
        )}/`,
        { method: "PATCH", headers, body: JSON.stringify({ is_curator: desired }) }
      );
      setRowStatus("Saved.", false);
      clearLiveStatusLater(rowStatus);
    } catch (e2) {
      target.checked = !desired;
      console.error("Failed to update member curator status", { groupId, userId, e2 });
      const msg = extractApiErrorMessage(e2);
      const fieldMsg = summarizeFieldErrors(e2 && e2.body ? e2.body : null);
      setRowStatus(fieldMsg || msg, true);
      setStatus(membersStatus, fieldMsg || msg, true);
      setGlobalError(fieldMsg || msg);
    } finally {
      target.disabled = false;
    }
  });

  return { membersCtl };
}
