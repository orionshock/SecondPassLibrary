import { fetchJSONWithOptions, getCsrfToken } from "../api.js";
import { $, loadMeAndInitShell, setGlobalError, visible } from "../layout.js";
import { setStatus } from "../ui/status.js";
import { groupMutationErrorMessage, isManagerOrOwner } from "./shared.js";

export async function initGroupNew() {
  const me = await loadMeAndInitShell();
  setGlobalError("");

  const root = $("#group-new-root");
  const notAllowedEl = $("#group-new-not-allowed");
  const form = $("#group-new-form");
  const nameInput = $("#group-new-name");
  const descInput = $("#group-new-description");
  const statusEl = $("#group-new-status");

  if (!root || !notAllowedEl || !form || !nameInput || !descInput || !statusEl) return;

  if (!isManagerOrOwner(me)) {
    visible(notAllowedEl, true);
    visible(root, false);
    return;
  }

  visible(notAllowedEl, false);
  visible(root, true);

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    setStatus(statusEl, "Creating...", false);
    setGlobalError("");

    try {
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json", "Content-Type": "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;

      const payload = {
        name: String(nameInput.value || "").trim(),
        description: String(descInput.value || "").trim(),
      };

      const created = await fetchJSONWithOptions("/api/v1/library/groups/", {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });

      const id = created && created.id ? String(created.id) : "";
      if (!id) {
        setStatus(statusEl, "Created, but response was missing id.", true);
        return;
      }
      window.location.href = `/groups/${encodeURIComponent(id)}/edit/`;
    } catch (err) {
      console.error("Failed to create group", err);
      const msg = groupMutationErrorMessage(err, "Failed to create group.");
      setStatus(statusEl, msg, true);
      setGlobalError(msg);
    }
  });
}
