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

export function renderMembershipControls(groups) {
  const list = Array.isArray(groups) ? groups : [];
  if (!list.length) return '<div class="muted">No group memberships.</div>';

  return list
    .map((g) => {
      const groupId = g.id ? String(g.id) : "";
      const membershipId = g.membership_id ? String(g.membership_id) : "";
      const isCurator = !!g.is_curator;
      const isPublic = !!g.is_public_group;

      const saveDisabled = isPublic ? "disabled" : "";
      const note = isPublic
        ? '<div class="muted">Public is the default/fallback group. Curator assignment is not available; removal is allowed when another membership remains (final removal restores Public).</div>'
        : "";

      return `
          <article class="book">
            <h3 class="book__title">${renderGroupBadge(g).outerHTML}</h3>
            <div class="book__meta">
              <div class="badge-row">
                <span class="pill">Member</span>
                ${isCurator ? '<span class="pill">Curator</span>' : ""}
                <label><input type="checkbox" data-action="membership-curator" data-group-id="${escapeHtml(groupId)}" data-membership-id="${escapeHtml(membershipId)}" ${isCurator ? "checked" : ""} ${isPublic ? "disabled" : ""} /> Curator</label>
              </div>
              ${note}
            </div>
            <div style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap;">
              <button class="button" type="button" data-action="membership-save" data-group-id="${escapeHtml(groupId)}" data-membership-id="${escapeHtml(membershipId)}" ${saveDisabled}>Save</button>
              <button class="icon-button" type="button" data-action="membership-remove" data-group-id="${escapeHtml(groupId)}" data-membership-id="${escapeHtml(membershipId)}" aria-label="Remove membership" title="Remove membership"><span class="material-symbols-outlined" aria-hidden="true">remove_circle</span></button>
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

  membershipsResults.addEventListener("click", async (e) => {
    const source = e.target;
    if (!source || source.nodeType !== 1) return;
    const target = source.closest("[data-action]");
    if (!target || !membershipsResults.contains(target)) return;
    const action = target.getAttribute("data-action");
    if (action !== "membership-save" && action !== "membership-remove") return;

    const groupId = target.getAttribute("data-group-id") || "";
    const membershipId = target.getAttribute("data-membership-id") || "";
    if (!groupId || !membershipId) {
      setStatus(membershipsStatus, "Missing membership identifiers.", true);
      return;
    }

    try {
      setStatus(membershipsStatus, action === "membership-save" ? "Saving..." : "Removing...", false);
      setGlobalError("");

      const csrf = getCsrfToken();
      const headers = { Accept: "application/json", "Content-Type": "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;

      if (action === "membership-save") {
        const container = target.closest("article");
        const curatorInput = container ? container.querySelector('input[data-action="membership-curator"]') : null;
        const isCurator = !!(curatorInput && curatorInput.checked);
        await fetchJSONWithOptions(
          `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/${encodeURIComponent(String(membershipId))}/`,
          {
            method: "PATCH",
            headers,
            body: JSON.stringify({ is_curator: isCurator }),
          }
        );
      } else {
        await fetchJSONWithOptions(
          `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/${encodeURIComponent(String(membershipId))}/`,
          { method: "DELETE", headers }
        );
      }

      await refreshUserAndMemberships();
      setStatus(membershipsStatus, action === "membership-save" ? "Saved." : "Removed.", false);
    } catch (e2) {
      console.error("Membership action failed", { action, groupId, membershipId, e2 });
      const msg = extractApiErrorMessage(e2);
      setStatus(membershipsStatus, msg, true);
      setGlobalError(msg);
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
        body: JSON.stringify({ user: String(userId), is_curator: isCurator }),
      });

      await refreshUserAndMemberships();
      setStatus(addStatus, "Added.", false);
    } catch (e2) {
      console.error("Failed to add membership", { userId, e2 });
      const msg = extractApiErrorMessage(e2);
      const fieldMsg = summarizeFieldErrors(e2 && e2.body ? e2.body : null);
      setStatus(addStatus, fieldMsg ? `${msg} (${fieldMsg})` : msg, true);
      setGlobalError(msg);
    } finally {
      setAddFormEnabled(true);
    }
  });
}
