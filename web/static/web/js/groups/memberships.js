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
      ? "Public is the default/fallback group. Public cannot have curators; role remains reader. Public membership can be removed when another group remains (final removal restores Public)."
      : membersNote.textContent;
    addMemberRole.value = "reader";
    const curatorOpt = addMemberRole.querySelector('option[value=\"curator\"]');
    if (curatorOpt) curatorOpt.disabled = true;
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
    const role = isPublicGroup ? "reader" : addMemberRole.value;
    if (!userId) {
      setAddMemberStatus("Choose a user.", true);
      return;
    }

    try {
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json", "Content-Type": "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;

      await fetchJSONWithOptions(`/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/`, {
        method: "POST",
        headers,
        body: JSON.stringify({ user: Number(userId), role }),
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
    const target = e.target;
    if (!target || target.nodeType !== 1) return;
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
      const select = membersResults.querySelector(
        `select[data-action=\"member-role\"][data-membership-id=\"${membershipId}\"]`
      );
      const role = select ? select.value : "reader";
      setStatus(membersStatus, "Saving...", false);
      try {
        const csrf = getCsrfToken();
        const headers = { Accept: "application/json", "Content-Type": "application/json" };
        if (csrf) headers["X-CSRFToken"] = csrf;

        await fetchJSONWithOptions(
          `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/${encodeURIComponent(
            String(membershipId)
          )}/`,
          { method: "PATCH", headers, body: JSON.stringify({ role }) }
        );
        await membersCtl.reloadFirstPage();
      } catch (e2) {
        console.error("Failed to update member role", { groupId, membershipId, e2 });
        setStatus(membersStatus, extractApiErrorMessage(e2), true);
        setGlobalError(extractApiErrorMessage(e2));
      }
    }
  });

  return { membersCtl };
}
