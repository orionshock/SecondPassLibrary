import { extractApiErrorMessage, fetchJSONWithOptions, getCsrfToken } from "../api.js";
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

  try {
    const users = await loadAllManageableUsers();
    addMemberUser.textContent = "";
    for (const u of users) {
      const opt = document.createElement("option");
      opt.value = String(u.id);
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

    const userId = addMemberUser.value;
    if (!userId) {
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
        body: JSON.stringify({ user: Number(userId), is_curator: isCurator }),
      });

      setAddMemberStatus("Added.", false);
      await membersCtl.reloadFirstPage();
    } catch (e2) {
      console.error("Failed to add member", { groupId, e2 });
      setAddMemberStatus(extractApiErrorMessage(e2), true);
      setGlobalError(extractApiErrorMessage(e2));
    }
  });

  membersResults.addEventListener("click", async (e) => {
    const source = e.target;
    if (!source || source.nodeType !== 1) return;
    const target = source.closest("[data-action]");
    if (!target || !membersResults.contains(target)) return;
    const action = target.getAttribute("data-action");
    const membershipId = target.getAttribute("data-membership-id");
    if (!action || !membershipId) return;

    if (action === "member-remove") {
      setStatus(membersStatus, "Removing...", false);
      try {
        const csrf = getCsrfToken();
        const headers = { Accept: "application/json" };
        if (csrf) headers["X-CSRFToken"] = csrf;

        await fetchJSONWithOptions(
          `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/${encodeURIComponent(
            String(membershipId)
          )}/`,
          { method: "DELETE", headers }
        );
        await membersCtl.reloadFirstPage();
      } catch (e2) {
        console.error("Failed to remove member", { groupId, membershipId, e2 });
        setStatus(membersStatus, extractApiErrorMessage(e2), true);
        setGlobalError(extractApiErrorMessage(e2));
      }
    }

    if (action === "member-save") {
      const checkbox = membersResults.querySelector(
        `input[data-action=\"member-curator\"][data-membership-id=\"${membershipId}\"]`
      );
      const isCurator = !!(checkbox && checkbox.checked);
      setStatus(membersStatus, "Saving...", false);
      try {
        const csrf = getCsrfToken();
        const headers = { Accept: "application/json", "Content-Type": "application/json" };
        if (csrf) headers["X-CSRFToken"] = csrf;

        await fetchJSONWithOptions(
          `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/${encodeURIComponent(
            String(membershipId)
          )}/`,
          { method: "PATCH", headers, body: JSON.stringify({ is_curator: isCurator }) }
        );
        await membersCtl.reloadFirstPage();
      } catch (e2) {
        console.error("Failed to update member curator status", { groupId, membershipId, e2 });
        setStatus(membersStatus, extractApiErrorMessage(e2), true);
        setGlobalError(extractApiErrorMessage(e2));
      }
    }
  });

  return { membersCtl };
}
