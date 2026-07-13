import {
  extractApiErrorMessage,
  fetchJSON,
  fetchJSONWithOptions,
  getCsrfToken,
  summarizeFieldErrors,
} from "../api.js";
import { escapeHtml, setGlobalError, visible } from "../layout.js";
import { renderGroupBadge } from "../ui/groups.js";
import { setStatus } from "../ui/status.js";

export function renderGroupsReadOnly(groups) {
  if (!Array.isArray(groups) || groups.length === 0) return '<div class="muted">No group memberships.</div>';
  return groups
    .map((g) => {
      const href = g.id ? `/groups/${encodeURIComponent(String(g.id))}/` : "#";
      const groupBadge = renderGroupBadge(g, { compact: true }).outerHTML;
      const indicators = ["Member"];
      if (g.is_curator) indicators.push("Curator");
      return `<div><a href="${escapeHtml(href)}">${groupBadge}</a> <span class="muted">(${escapeHtml(indicators.join(", "))})</span></div>`;
    })
    .join("");
}

function descriptionForGroup(group, groupDetailsById) {
  const ownDescription = group && group.description ? String(group.description).trim() : "";
  if (ownDescription) return ownDescription;
  const groupId = group && group.id != null ? String(group.id) : "";
  const detail = groupId ? groupDetailsById.get(groupId) : null;
  return detail && detail.description ? String(detail.description).trim() : "";
}

export function renderMembershipControls(groups, allGroups = [], profileId = "") {
  const list = Array.isArray(groups) ? groups : [];
  if (!list.length) return '<div class="muted">No group memberships.</div>';
  const groupDetailsById = new Map(
    (Array.isArray(allGroups) ? allGroups : [])
      .filter((g) => g && g.id != null)
      .map((g) => [String(g.id), g])
  );

  return list
    .map((g) => {
      const groupId = g.id ? String(g.id) : "";
      const isCurator = !!g.is_curator;
      const isPublic = !!g.is_public_group;

      const note = isPublic
        ? '<div class="membership-row__note muted">Public fallback group; curator unavailable.</div>'
        : "";
      const groupBadge = renderGroupBadge(g).outerHTML;
      const description = descriptionForGroup(g, groupDetailsById);
      const titleAttr = description ? ` title="${escapeHtml(description)}"` : "";
      const curatorControl = isPublic
        ? ""
        : `
              <label class="membership-row__curator">
                <input type="checkbox" data-action="membership-curator" data-group-id="${escapeHtml(groupId)}" data-user-id="${escapeHtml(profileId)}" ${isCurator ? "checked" : ""} />
                <span>Curator</span>
              </label>
            `.trim();

      return `
          <article class="membership-row">
            <div class="membership-row__actions">
              <button class="icon-button icon-button--danger" type="button" data-action="membership-remove" data-group-id="${escapeHtml(groupId)}" data-user-id="${escapeHtml(profileId)}" aria-label="Remove membership" title="Remove membership"><span class="material-symbols-outlined" aria-hidden="true">remove_circle</span></button>
            </div>
            <div class="membership-row__group"${titleAttr}>${groupBadge}</div>
            <div class="membership-row__controls">
              ${curatorControl}
              ${note}
              <span class="membership-row__status muted" aria-live="polite"></span>
            </div>
          </article>
        `.trim();
    })
    .join("");
}

export async function loadAllGroups() {
  const groups = [];
  let url = "/api/v1/library/groups/";
  for (let i = 0; i < 10 && url; i++) {
    const payload = await fetchJSON(url);
    const results = Array.isArray(payload && payload.results) ? payload.results : [];
    for (const g of results) groups.push(g);
    url = payload.next || null;
  }
  return groups;
}

export function refreshAddGroupOptions({ allGroups, userGroups, addGroupSelect, addSubmitBtn }) {
  const existing = new Set((Array.isArray(userGroups) ? userGroups : []).map((g) => String(g.id)));
  addGroupSelect.innerHTML = "";

  const selectable = (Array.isArray(allGroups) ? allGroups : [])
    .filter((g) => g && g.id && !existing.has(String(g.id)))
    .filter((g) => !(g && g.is_public_group));

  if (!selectable.length) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "(no groups available)";
    addGroupSelect.appendChild(opt);
    addGroupSelect.disabled = true;
    addSubmitBtn.disabled = true;
    return;
  }

  addGroupSelect.disabled = false;
  addSubmitBtn.disabled = false;

  for (const g of selectable) {
    const opt = document.createElement("option");
    opt.value = String(g.id);
    opt.textContent = g.name ? String(g.name) : String(g.id);
    addGroupSelect.appendChild(opt);
  }
}

export function initUserMembershipsManager({
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
}) {
  function setAddFormEnabled(on) {
    const disabled = !on;
    addGroupSelect.disabled = disabled;
    addRoleSelect.disabled = disabled;
    addSubmitBtn.disabled = disabled;
  }

  if (!canManageMemberships) {
    visible(membershipsCard, false);
    return;
  }

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

  membershipsResults.addEventListener("click", async (e) => {
    const source = e.target;
    if (!source || source.nodeType !== 1) return;
    const target = source.closest("[data-action]");
    if (!target || !membershipsResults.contains(target)) return;
    const action = target.getAttribute("data-action");
    if (action !== "membership-remove") return;

    const groupId = target.getAttribute("data-group-id") || "";
    const userId = target.getAttribute("data-user-id") || "";
    const row = target.closest(".membership-row");
    const rowStatus = row ? row.querySelector(".membership-row__status") : null;
    function setRowStatus(text, isError) {
      if (!rowStatus) return;
      rowStatus.textContent = text || "";
      rowStatus.classList.toggle("error", !!isError);
    }

    if (!groupId || !userId) {
      setRowStatus("Missing membership identifiers.", true);
      return;
    }
    if (!window.confirm("Remove this user from the group?")) return;

    try {
      setRowStatus("Removing...", false);
      setGlobalError("");

      const csrf = getCsrfToken();
      const headers = { Accept: "application/json", "Content-Type": "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;

      await fetchJSONWithOptions(
        `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/${encodeURIComponent(String(userId))}/`,
        { method: "DELETE", headers }
      );

      setRowStatus("Removed.", false);
      await refreshUserAndMemberships();
    } catch (e2) {
      console.error("Membership action failed", { action, groupId, userId, e2 });
      const msg = extractApiErrorMessage(e2);
      setRowStatus(msg, true);
      setGlobalError(msg);
    }
  });

  membershipsResults.addEventListener("change", async (e) => {
    const source = e.target;
    if (!source || source.nodeType !== 1) return;
    const target = source.closest('input[data-action="membership-curator"]');
    if (!target || !membershipsResults.contains(target)) return;

    const groupId = target.getAttribute("data-group-id") || "";
    const userId = target.getAttribute("data-user-id") || "";
    const row = target.closest(".membership-row");
    const rowStatus = row ? row.querySelector(".membership-row__status") : null;
    const desired = !!target.checked;
    function setRowStatus(text, isError) {
      if (!rowStatus) return;
      rowStatus.textContent = text || "";
      rowStatus.classList.toggle("error", !!isError);
    }

    if (!groupId || !userId) {
      setRowStatus("Missing membership identifiers.", true);
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
        `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/${encodeURIComponent(String(userId))}/`,
        {
          method: "PATCH",
          headers,
          body: JSON.stringify({ is_curator: desired }),
        }
      );

      setRowStatus("Saved.", false);
      clearLiveStatusLater(rowStatus);
    } catch (e2) {
      target.checked = !desired;
      console.error("Curator update failed", { groupId, userId, e2 });
      const msg = extractApiErrorMessage(e2);
      const fieldMsg = summarizeFieldErrors(e2 && e2.body ? e2.body : null);
      setRowStatus(fieldMsg || msg, true);
      setGlobalError(fieldMsg || msg);
    } finally {
      target.disabled = false;
    }
  });

  addForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    setGlobalError("");
    setStatus(addStatus, "Adding...", false);
    setAddFormEnabled(false);

    const groupId = addGroupSelect.value || "";
    if (!groupId) {
      setStatus(addStatus, "Select a group.", true);
      setAddFormEnabled(true);
      return;
    }

    try {
      const isCurator = !!addRoleSelect.checked;
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json", "Content-Type": "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;

      await fetchJSONWithOptions(`/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/`, {
        method: "POST",
        headers,
        body: JSON.stringify({ user_id: String(profileId), is_curator: isCurator }),
      });

      await refreshUserAndMemberships();
      setStatus(addStatus, "Added.", false);
    } catch (e2) {
      console.error("Failed to add membership", { profileId, e2 });
      const msg = extractApiErrorMessage(e2);
      const fieldMsg = summarizeFieldErrors(e2 && e2.body ? e2.body : null);
      setStatus(addStatus, fieldMsg || msg, true);
      setGlobalError(fieldMsg || msg);
    } finally {
      setAddFormEnabled(true);
    }
  });
}
