import { $, loadMeAndInitShell, setGlobalErrorFromError, setText, visible } from "./layout.js";
import { fetchJSON, patchJSON } from "./api.js";

function setEditing(on) {
  visible($("#server-settings-edit-btn"), !on);
  visible($("#server-settings-save-btn"), on);
  visible($("#server-settings-cancel-btn"), on);
  visible($("#server-settings-name-display"), !on);
  visible($("#server-settings-description-display"), !on);
  visible($("#server-settings-name-input"), on);
  visible($("#server-settings-description-input"), on);
}

function setStatus(text) {
  setText($("#server-settings-status"), text || "");
}

function fill(identity) {
  const name = identity && identity.server_name ? String(identity.server_name) : "";
  const desc = identity && identity.server_description ? String(identity.server_description) : "";
  setText($("#server-settings-name-display"), name || "(unset)");
  setText($("#server-settings-description-display"), desc || "(empty)");
  const nameInput = $("#server-settings-name-input");
  const descInput = $("#server-settings-description-input");
  if (nameInput) nameInput.value = name;
  if (descInput) descInput.value = desc;
}

export async function initServerSettings() {
  const me = await loadMeAndInitShell();
  if (!me || !me.is_owner) return;

  setEditing(false);
  setStatus("Loading...");

  let identity;
  try {
    identity = await fetchJSON("/api/v1/server/settings/");
  } catch (e) {
    console.error("Failed to load server settings", e);
    setGlobalErrorFromError(e, "Failed to load server settings:");
    setStatus("Failed to load.");
    return;
  }

  fill(identity);
  setStatus("");

  const editBtn = $("#server-settings-edit-btn");
  const cancelBtn = $("#server-settings-cancel-btn");
  const form = $("#server-settings-form");
  if (editBtn) {
    editBtn.addEventListener("click", () => {
      setEditing(true);
      setStatus("");
    });
  }
  if (cancelBtn) {
    cancelBtn.addEventListener("click", () => {
      fill(identity);
      setEditing(false);
      setStatus("");
    });
  }
  if (form) {
    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const nameInput = $("#server-settings-name-input");
      const descInput = $("#server-settings-description-input");
      const server_name = nameInput ? nameInput.value : "";
      const server_description = descInput ? descInput.value : "";
      setStatus("Saving...");
      try {
        const payload = {};
        payload.server_name = server_name;
        payload.server_description = server_description;
        identity = await patchJSON("/api/v1/server/settings/", payload);
        fill(identity);
        setEditing(false);
        setStatus("Saved.");
      } catch (e) {
        console.error("Failed to save server settings", e);
        setGlobalErrorFromError(e, "Failed to save:");
        setStatus("Failed to save.");
      }
    });
  }
}
