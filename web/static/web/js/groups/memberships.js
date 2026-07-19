import { fetchJSON, fetchJSONWithOptions, getCsrfToken } from "../api.js";
import { setGlobalError, visible } from "../layout.js";
import { createGroupEditPager } from "./edit_pagination.js";
import {
  canManageGroupMemberships,
  groupMutationErrorMessage,
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
  addMemberSearch,
  addMemberUser,
  addMemberChoices,
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

  function clearMemberChoices() {
    addMemberChoices.textContent = "";
    visible(addMemberChoices, false);
    addMemberSearch.setAttribute("aria-expanded", "false");
  }

  const membersCtl = await createGroupEditPager({
    key: "members",
    tab: "members",
    statusEl: membersStatus,
    resultsEl: membersResults,
    nextBtn: membersNext,
    prevBtn: membersPrev,
    initialUrl: `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/`,
    emptyText: "No members.",
    render: (payload) =>
      allowMembershipManage ? renderMembersManage(payload, { isPublicGroup }) : renderMembersReadOnly(payload),
    loadErrorText: "Unable to load group members.",
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

  const minimumQueryLength = 2;
  const searchDelayMs = 250;
  let searchTimer = null;
  let searchSequence = 0;

  async function loadMemberChoices(query, sequence) {
    setAddMemberStatus("Searching...", false);
    const params = new URLSearchParams({ q: query, exclude_group: String(groupId) });
    try {
      const payload = await fetchJSON(`/api/v1/accounts/user-choices/?${params.toString()}`);
      if (sequence !== searchSequence) return;

      clearMemberChoices();
      const choices = Array.isArray(payload && payload.results) ? payload.results : [];
      if (!choices.length) {
        setAddMemberStatus("No matching users.", false);
        return;
      }

      for (const choice of choices) {
        const profileId = choice && choice.profile_id ? String(choice.profile_id) : "";
        const username = choice && choice.username ? String(choice.username) : "";
        if (!profileId || !username) continue;
        const button = document.createElement("button");
        button.type = "button";
        button.className = "member-choice-picker__option";
        button.setAttribute("role", "option");
        button.setAttribute("data-profile-id", profileId);
        button.setAttribute("data-username", username);
        button.textContent = username;
        addMemberChoices.appendChild(button);
      }

      if (!addMemberChoices.children.length) {
        setAddMemberStatus("No matching users.", false);
        return;
      }
      visible(addMemberChoices, true);
      addMemberSearch.setAttribute("aria-expanded", "true");
      setAddMemberStatus(payload.next ? "Keep typing to narrow the results." : "Choose a username.", false);
    } catch (error) {
      if (sequence !== searchSequence) return;
      console.error("Failed to search user choices", { groupId, error });
      clearMemberChoices();
      setAddMemberStatus("Could not search users.", true);
    }
  }

  addMemberSearch.addEventListener("input", () => {
    addMemberUser.value = "";
    clearMemberChoices();
    searchSequence += 1;
    const sequence = searchSequence;
    if (searchTimer) window.clearTimeout(searchTimer);

    const query = String(addMemberSearch.value || "").trim();
    if (!query) {
      setAddMemberStatus("", false);
      return;
    }
    if (query.length < minimumQueryLength) {
      setAddMemberStatus(`Type at least ${minimumQueryLength} characters.`, false);
      return;
    }

    searchTimer = window.setTimeout(() => {
      loadMemberChoices(query, sequence);
    }, searchDelayMs);
  });

  addMemberChoices.addEventListener("click", (event) => {
    const source = event.target;
    if (!source || source.nodeType !== 1) return;
    const choice = source.closest("button[data-profile-id]");
    if (!choice || !addMemberChoices.contains(choice)) return;
    const profileId = choice.getAttribute("data-profile-id") || "";
    const username = choice.getAttribute("data-username") || "";
    if (!profileId || !username) return;
    addMemberUser.value = profileId;
    addMemberSearch.value = username;
    clearMemberChoices();
    setAddMemberStatus(`Selected ${username}.`, false);
  });

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
      addMemberUser.value = "";
      addMemberSearch.value = "";
      clearMemberChoices();
      await membersCtl.reloadFirstPage();
    } catch (e2) {
      console.error("Failed to add member", { groupId, e2 });
      const msg = groupMutationErrorMessage(e2, "Failed to add member.");
      setAddMemberStatus(msg, true);
      setGlobalError(msg);
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
        const msg = groupMutationErrorMessage(e2, "Failed to remove member.");
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
      const msg = groupMutationErrorMessage(e2, "Failed to update curator status.");
      setRowStatus(msg, true);
      setStatus(membersStatus, msg, true);
      setGlobalError(msg);
    } finally {
      target.disabled = false;
    }
  });

  return { membersCtl };
}
