import { $, loadMeAndInitShell, setGlobalErrorFromError, setText, visible } from "../layout.js";
import { fetchJSON, patchJSON } from "../api.js";
import { setStatus } from "../ui/status.js";

function setEditing(on) {
  visible($("#server-settings-edit-btn"), !on);
  visible($("#server-settings-save-btn"), on);
  visible($("#server-settings-cancel-btn"), on);
  visible($("#server-settings-name-display"), !on);
  visible($("#server-settings-description-display"), !on);
  visible($("#server-settings-banner-display"), !on);
  visible($("#server-settings-public-name-display"), !on);
  visible($("#server-settings-public-description-display"), !on);
  visible($("#server-settings-advanced-groups-display"), !on);
  visible($("#server-settings-name-input"), on);
  visible($("#server-settings-description-input"), on);
  visible($("#server-settings-banner-input"), on);
  visible($("#server-settings-public-name-input"), on);
  visible($("#server-settings-public-description-input"), on);
  visible($("#server-settings-advanced-groups-edit"), on);
}

function fill(identity) {
  const name = identity && identity.server_name ? String(identity.server_name) : "";
  const desc = identity && identity.server_description ? String(identity.server_description) : "";
  const banner = identity && identity.server_banner_message ? String(identity.server_banner_message) : "";
  const publicName = identity && identity.public_group_name ? String(identity.public_group_name) : "";
  const publicDesc = identity && identity.public_group_description ? String(identity.public_group_description) : "";
  const advancedGroups = !!(identity && identity.advanced_library_groups_enabled);
  setText($("#server-settings-name-display"), name || "(unset)");
  setText($("#server-settings-description-display"), desc || "(empty)");
  setText($("#server-settings-banner-display"), banner || "(empty)");
  setText($("#server-settings-public-name-display"), publicName || "(unset)");
  setText($("#server-settings-public-description-display"), publicDesc || "(empty)");
  setText($("#server-settings-advanced-groups-display"), advancedGroups ? "Enabled" : "Disabled");
  const nameInput = $("#server-settings-name-input");
  const descInput = $("#server-settings-description-input");
  const bannerInput = $("#server-settings-banner-input");
  const publicNameInput = $("#server-settings-public-name-input");
  const publicDescInput = $("#server-settings-public-description-input");
  const advancedGroupsInput = $("#server-settings-advanced-groups-input");
  if (nameInput) nameInput.value = name;
  if (descInput) descInput.value = desc;
  if (bannerInput) bannerInput.value = banner;
  if (publicNameInput) publicNameInput.value = publicName;
  if (publicDescInput) publicDescInput.value = publicDesc;
  if (advancedGroupsInput) advancedGroupsInput.checked = advancedGroups;
}

export async function initServerSettings() {
  const me = await loadMeAndInitShell();
  if (!me || !me.is_owner) return;

  setEditing(false);
  setStatus("#server-settings-status", "Loading...");

  let identity;
  try {
    identity = await fetchJSON("/api/v1/server/settings/");
  } catch (e) {
    console.error("Failed to load server settings", e);
    setGlobalErrorFromError(e, "Failed to load server settings:");
    setStatus("#server-settings-status", "Failed to load.");
    return;
  }

  fill(identity);
  setStatus("#server-settings-status", "");

  const editBtn = $("#server-settings-edit-btn");
  const cancelBtn = $("#server-settings-cancel-btn");
  const form = $("#server-settings-form");
  if (editBtn) {
    editBtn.addEventListener("click", () => {
      setEditing(true);
      setStatus("#server-settings-status", "");
    });
  }
  if (cancelBtn) {
    cancelBtn.addEventListener("click", () => {
      fill(identity);
      setEditing(false);
      setStatus("#server-settings-status", "");
    });
  }
  if (form) {
    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const nameInput = $("#server-settings-name-input");
      const descInput = $("#server-settings-description-input");
      const bannerInput = $("#server-settings-banner-input");
      const server_name = nameInput ? nameInput.value : "";
      const server_description = descInput ? descInput.value : "";
      const server_banner_message = bannerInput ? bannerInput.value : "";
      const publicNameInput = $("#server-settings-public-name-input");
      const publicDescInput = $("#server-settings-public-description-input");
      const advancedGroupsInput = $("#server-settings-advanced-groups-input");
      setStatus("#server-settings-status", "Saving...");
      try {
        const payload = {};
        payload.server_name = server_name;
        payload.server_description = server_description;
        payload.server_banner_message = server_banner_message;
        payload.public_group_name = publicNameInput ? publicNameInput.value : "";
        payload.public_group_description = publicDescInput ? publicDescInput.value : "";
        payload.advanced_library_groups_enabled = advancedGroupsInput ? advancedGroupsInput.checked : false;
        identity = await patchJSON("/api/v1/server/settings/", payload);
        fill(identity);
        setEditing(false);
        setStatus("#server-settings-status", "Saved.");
      } catch (e) {
        console.error("Failed to save server settings", e);
        setGlobalErrorFromError(e, "Failed to save:");
        setStatus("#server-settings-status", "Failed to save.");
      }
    });
  }
}
