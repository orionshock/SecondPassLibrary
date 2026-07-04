import {
  extractApiErrorMessage,
  fetchJSON,
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
    (group) =>
      group &&
      !group.is_public_group &&
      group.is_curator === true
  );
}

export function manageableShelfGroups(me, groups) {
  const availableGroups = Array.isArray(groups) ? groups : [];
  if (!me) return [];

  return availableGroups.filter(
    (group) =>
      group &&
      group.capabilities &&
      group.capabilities.can_curate === true
  );
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
  const visibilityEl = $("#shelf-new-visibility");
  const ownerGroupEl = $("#shelf-new-owner-group");
  const ownerTypeRow = $("#shelf-new-owner-type-row");
  const ownerTypeRowValue = $("#shelf-new-owner-type-row-v");
  const ownerGroupRow = $("#shelf-new-owner-group-row");
  const ownerGroupRowValue = $("#shelf-new-owner-group-row-v");
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
  const canCreateGroupShelf = groupUiEnabled && canCreateGroupShelves(me);
  ownerTypeEl.value = "user";
  ownerGroupEl.disabled = true;
  visible(ownerTypeRow, canCreateGroupShelf);
  visible(ownerTypeRowValue, canCreateGroupShelf);
  visible(ownerGroupRow, canCreateGroupShelf);
  visible(ownerGroupRowValue, canCreateGroupShelf);

  let results = [];
  if (canCreateGroupShelf) {
    const groups = await fetchJSON("/api/v1/library/groups/");
    const availableGroups = Array.isArray(groups && groups.results)
      ? groups.results
      : [];
    results = manageableShelfGroups(me, availableGroups);
  }

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
  if (canCreateGroupShelf) {
    if (preOwnerType === "group") ownerTypeEl.value = "group";
    else if (preOwnerGroup) ownerTypeEl.value = "group";
    if (preOwnerGroup) ownerGroupEl.value = preOwnerGroup;
  }

  function syncOwnerUI() {
    const isGroup =
      canCreateGroupShelf && ownerTypeEl.value === "group";
    visibilityEl.disabled = isGroup;
    ownerGroupEl.disabled = !isGroup;
    if (isGroup) visibilityEl.value = "private";
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
      canCreateGroupShelf && ownerTypeEl.value === "group"
        ? "group"
        : "user";
    const body = {
      name: nameEl.value || "",
      description: descEl.value || "",
      owner_type: ownerType,
    };
    if (ownerType === "user") body.visibility = visibilityEl.value;
    if (ownerType === "group") body.owner_group = ownerGroupEl.value;

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
