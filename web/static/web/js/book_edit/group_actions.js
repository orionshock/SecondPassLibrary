import {
  extractApiErrorMessage,
  fetchJSONWithOptions,
  getCsrfToken,
  summarizeFieldErrors,
} from "../api.js";
import { setStatus } from "../ui/status.js";

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
    setStatus(groupsStatusEl, "Removing...", false);
    try {
      await fetchJSONWithOptions(
        `/api/v1/library/groups/${encodeURIComponent(String(gid))}/books/${encodeURIComponent(String(bookId))}/`,
        { method: "DELETE", headers: { Accept: "application/json", "X-CSRFToken": csrf } }
      );
      setStatus(groupsStatusEl, "", false);
      await refreshBook();
    } catch (e) {
      console.error("Remove group assignment failed", e);
      setStatus(groupsStatusEl, "Remove failed.", true);
      setError(`Failed to remove from group: ${extractApiErrorMessage(e)}`);
    }
  });

  groupsAddFormEl.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    setError("");
    setStatus(groupsAddStatusEl, "", false);
    const gid = (groupsAddSelectEl.value || "").trim();
    if (!gid) return;
    const csrf = getCsrfToken();
    if (!csrf) {
      setError("Missing CSRF token cookie. Reload the page and try again.");
      return;
    }
    setStatus(groupsAddStatusEl, "Adding...", false);
    try {
      await fetchJSONWithOptions(`/api/v1/library/groups/${encodeURIComponent(String(gid))}/books/`, {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({ book: String(bookId) }),
      });
      setStatus(groupsAddStatusEl, "Added.", false);
      await refreshBook();
    } catch (e) {
      console.error("Add group assignment failed", e);
      setStatus(groupsAddStatusEl, "Add failed.", true);
      const msg = extractApiErrorMessage(e);
      const body = e && e.body ? e.body : null;
      const fields = summarizeFieldErrors(body);
      setError(fields ? `${msg} (${fields})` : msg);
    }
  });
}
