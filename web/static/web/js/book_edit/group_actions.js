import {
  extractApiErrorMessage,
  fetchJSONWithOptions,
  getCsrfToken,
  summarizeFieldErrors,
} from "../api.js";
import { setInlineStatus } from "./shared.js";

export function bindGroupActions({
  bookId,
  groupsEl,
  groupsStatusEl,
  groupsAddFormEl,
  groupsAddSelectEl,
  groupsAddStatusEl,
  refreshBook,
  setError,
}) {
  groupsEl.addEventListener("click", async (ev) => {
    const t = ev.target;
    if (!t || !t.getAttribute) return;
    const gid = t.getAttribute("data-group-remove-id");
    if (!gid) return;
    const csrf = getCsrfToken();
    if (!csrf) {
      setError("Missing CSRF token cookie. Reload the page and try again.");
      return;
    }
    setInlineStatus(groupsStatusEl, "Removing...", false);
    try {
      await fetchJSONWithOptions(
        `/api/v1/library/groups/${encodeURIComponent(String(gid))}/books/${encodeURIComponent(String(bookId))}/`,
        { method: "DELETE", headers: { Accept: "application/json", "X-CSRFToken": csrf } }
      );
      setInlineStatus(groupsStatusEl, "", false);
      await refreshBook();
    } catch (e) {
      console.error("Remove group assignment failed", e);
      setInlineStatus(groupsStatusEl, "Remove failed.", true);
      setError(`Failed to remove from group: ${extractApiErrorMessage(e)}`);
    }
  });

  groupsAddFormEl.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    setError("");
    setInlineStatus(groupsAddStatusEl, "", false);
    const gid = (groupsAddSelectEl.value || "").trim();
    if (!gid) return;
    const csrf = getCsrfToken();
    if (!csrf) {
      setError("Missing CSRF token cookie. Reload the page and try again.");
      return;
    }
    setInlineStatus(groupsAddStatusEl, "Adding...", false);
    try {
      await fetchJSONWithOptions(`/api/v1/library/groups/${encodeURIComponent(String(gid))}/books/`, {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({ book: String(bookId) }),
      });
      setInlineStatus(groupsAddStatusEl, "Added.", false);
      await refreshBook();
    } catch (e) {
      console.error("Add group assignment failed", e);
      setInlineStatus(groupsAddStatusEl, "Add failed.", true);
      const msg = extractApiErrorMessage(e);
      const body = e && e.body ? e.body : null;
      const fields = summarizeFieldErrors(body);
      setError(fields ? `${msg} (${fields})` : msg);
    }
  });
}
