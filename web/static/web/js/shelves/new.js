import {
  extractApiErrorMessage,
  fetchAllPaginatedResults,
  fetchJSONWithOptions,
  getCsrfToken,
} from "../api.js";
import { canManageLibrary } from "../auth.js";
import { $, advancedLibraryGroupsEnabled, loadMeAndInitShell, setGlobalError, visible } from "../layout.js";
import { setStatus } from "../ui/status.js";

export function canCreateGroupShelves(me) {
  if (!me) return false;
  if (canManageLibrary(me)) return true;

  const groups = Array.isArray(me.groups) ? me.groups : [];
  return groups.some(
    (membership) =>
      membership &&
      !membership.is_public_group &&
      membership.is_curator === true
  );
}

export function manageableShelfGroups(me, groups) {
  const availableGroups = Array.isArray(groups) ? groups : [];
  if (!me) return [];

  const broadAccess = canManageLibrary(me);
  const curatedGroupIds = new Set(
    (Array.isArray(me.groups) ? me.groups : [])
      .filter(
        (membership) =>
          membership && !membership.is_public_group && membership.is_curator === true
      )
      .map((membership) => String(membership.id))
  );

  return availableGroups.filter(
    (group) =>
      group &&
      group.id &&
      (broadAccess ||
        (!group.is_public_group && curatedGroupIds.has(String(group.id))))
  );
}

export function publicShelfGroup(me) {
  const groups = Array.isArray(me && me.groups) ? me.groups : [];
  return groups.find((group) => group && group.is_public_group === true) || null;
}

export async function loadAllShelfGroups() {
  return fetchAllPaginatedResults("/api/v1/library/groups/", {
    invalidResponseMessage: "Invalid group list response.",
    invalidContinuationMessage: "Invalid group pagination continuation.",
    repeatedContinuationMessage: "Group pagination continuation repeated.",
  });
}

export function requestedShelfGroup(search, groups) {
  const params = new URLSearchParams(search || "");
  const requestedId = params.get("owner_group") || "";
  if (!requestedId) return null;
  return (
    (Array.isArray(groups) ? groups : []).find(
      (group) => group && String(group.id) === String(requestedId)
    ) || null
  );
}

export function shelfCreatePayload({ name, description, ownerType, ownerGroup, visibility }) {
  const body = {
    name: name || "",
    description: description || "",
    owner_type: ownerType === "group" ? "group" : "user",
  };
  if (body.owner_type === "group") {
    body.owner_group = ownerGroup || "";
    body.visibility = "private";
  } else {
    body.visibility = visibility;
  }
  return body;
}

export function groupLoadErrorMessage(error) {
  const status = error && error.status ? Number(error.status) : null;
  return status
    ? `Unable to load owner groups (HTTP ${status}). Personal shelf creation is still available.`
    : "Unable to load owner groups. Personal shelf creation is still available.";
}

export async function initShelfNew() {
  const me = await loadMeAndInitShell();
  setGlobalError("");

  const statusEl = $("#shelf-new-status");
  const cardEl = $("#shelf-new-card");
  const errEl = $("#shelf-new-error");
  const formEl = $("#shelf-new-form");
  const nameEl = $("#shelf-new-name");
  const descEl = $("#shelf-new-description");
  const ownerTypeEl = $("#shelf-new-owner-type");
  const groupOwnerOption = ownerTypeEl
    ? ownerTypeEl.querySelector('option[value="group"]')
    : null;
  const visibilityEl = $("#shelf-new-visibility");
  const ownerGroupEl = $("#shelf-new-owner-group");
  const ownerTypeRow = $("#shelf-new-owner-type-row");
  const ownerTypeRowValue = $("#shelf-new-owner-type-row-v");
  const ownerGroupRow = $("#shelf-new-owner-group-row");
  const ownerGroupRowValue = $("#shelf-new-owner-group-row-v");
  const publicGroupHelpEl = $("#shelf-new-public-group-help");
  const submitStatusEl = $("#shelf-new-submit-status");
  if (
    !statusEl ||
    !cardEl ||
    !errEl ||
    !formEl ||
    !nameEl ||
    !descEl ||
    !ownerTypeEl ||
    !visibilityEl ||
    !ownerGroupEl ||
    !submitStatusEl
  )
    return;

  function setErr(msg) {
    errEl.textContent = msg || "";
    visible(errEl, !!msg);
  }

  setStatus(statusEl, "Loading...", false);
  setErr("");

  const groupUiEnabled = advancedLibraryGroupsEnabled();
  const publicGroup = publicShelfGroup(me);
  const canCreateAdvancedGroupShelf =
    groupUiEnabled && canCreateGroupShelves(me);
  const canCreateSimplePublicShelf =
    !groupUiEnabled && canManageLibrary(me) && !!publicGroup;
  const canCreateGroupShelf =
    canCreateAdvancedGroupShelf || canCreateSimplePublicShelf;
  ownerTypeEl.value = "user";
  if (groupOwnerOption) {
    groupOwnerOption.disabled = !canCreateGroupShelf;
    groupOwnerOption.textContent = canCreateSimplePublicShelf
      ? `${String(publicGroup.name || "Public/Common Room")} shelf`
      : "Group shelf";
  }
  ownerGroupEl.disabled = true;
  visible(ownerTypeRow, canCreateGroupShelf);
  visible(ownerTypeRowValue, canCreateGroupShelf);
  visible(ownerGroupRow, canCreateAdvancedGroupShelf);
  visible(ownerGroupRowValue, canCreateAdvancedGroupShelf);

  let results = [];
  let groupShelfAvailable = canCreateGroupShelf;
  let groupLoadFailed = false;
  if (canCreateAdvancedGroupShelf) {
    try {
      results = manageableShelfGroups(me, await loadAllShelfGroups());
    } catch (error) {
      console.error("Failed to load shelf owner groups", error);
      const message = groupLoadErrorMessage(error);
      setErr(message);
      setGlobalError(message);
      groupShelfAvailable = false;
      groupLoadFailed = true;
    }
  } else if (canCreateSimplePublicShelf) {
    results = [publicGroup];
  }

  if (canCreateAdvancedGroupShelf && !groupLoadFailed && results.length === 0) {
    setErr("No manageable owner groups are available. Personal shelf creation is still available.");
    groupShelfAvailable = false;
  }
  if (groupOwnerOption) groupOwnerOption.disabled = !groupShelfAvailable;

  ownerGroupEl.textContent = "";
  for (const g of results) {
    const opt = document.createElement("option");
    opt.value = String(g.id);
    opt.textContent = String(g.name || g.id);
    ownerGroupEl.appendChild(opt);
  }

  const qs = new URLSearchParams(window.location.search || "");
  const preOwnerType = qs.get("owner_type");
  const preOwnerGroup = qs.get("owner_group");
  const requestedGroup = requestedShelfGroup(window.location.search, results);
  if (groupShelfAvailable) {
    if (preOwnerType === "group" || requestedGroup) ownerTypeEl.value = "group";
    if (requestedGroup) ownerGroupEl.value = String(requestedGroup.id);
  }
  if (preOwnerGroup && !requestedGroup && !groupLoadFailed) {
    setErr("The requested owner group is not available for this account.");
  }

  function syncOwnerUI() {
    const isGroup =
      groupShelfAvailable && ownerTypeEl.value === "group";
    visibilityEl.disabled = isGroup;
    ownerGroupEl.disabled = !isGroup;
    if (isGroup) visibilityEl.value = "private";
    visible(publicGroupHelpEl, canCreateSimplePublicShelf && isGroup);
  }
  ownerTypeEl.addEventListener("change", syncOwnerUI);
  syncOwnerUI();

  visible(cardEl, true);
  setStatus(statusEl, "", false);

  formEl.addEventListener("submit", async (e) => {
    e.preventDefault();
    setGlobalError("");
    setErr("");
    setStatus(submitStatusEl, "Creating...", false);

    const ownerType =
      groupShelfAvailable && ownerTypeEl.value === "group"
        ? "group"
        : "user";
    if (ownerType === "group" && !ownerGroupEl.value) {
      setErr("Select an owner group.");
      setStatus(submitStatusEl, "", true);
      return;
    }
    const body = shelfCreatePayload({
      name: nameEl.value,
      description: descEl.value,
      ownerType,
      ownerGroup: ownerGroupEl.value,
      visibility: visibilityEl.value,
    });

    try {
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json", "Content-Type": "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;

      const created = await fetchJSONWithOptions("/api/v1/shelves/", {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      });

      setStatus(submitStatusEl, "", false);
      const id = created && created.id ? String(created.id) : "";
      window.location.href = id ? `/shelves/${encodeURIComponent(id)}/edit/` : "/shelves/";
    } catch (e2) {
      console.error("Failed to create shelf", e2);
      const msg = extractApiErrorMessage(e2);
      setErr(msg);
      setGlobalError(msg);
      setStatus(submitStatusEl, "", true);
    }
  });
}
