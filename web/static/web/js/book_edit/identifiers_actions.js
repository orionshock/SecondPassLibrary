import {
  extractApiErrorMessage,
  fetchJSON,
  fetchJSONWithOptions,
  getCsrfToken,
  summarizeFieldErrors,
} from "../api.js";
import { renderIdentifiersTable } from "./identifiers_file.js";
import { setStatus as setInlineStatus } from "../ui/status.js";

export async function refreshIdentifiersContext({
  bookId,
  identifiersStatusEl,
  identifiersEl,
  state,
  setError,
}) {
  setInlineStatus(identifiersStatusEl, "Loading...", false);
  try {
    const list = await fetchJSON(`/api/v1/library/books/${encodeURIComponent(String(bookId))}/identifiers/`);
    state.identifiers = Array.isArray(list) ? list : [];
    setInlineStatus(identifiersStatusEl, "", false);
    renderIdentifiersTable({ identifiers: state.identifiers, identifiersEl });
  } catch (e) {
    console.error("Failed to load identifiers", e);
    setInlineStatus(identifiersStatusEl, "Failed to load.", true);
    setError(`Failed to load identifiers: ${extractApiErrorMessage(e)}`);
    state.identifiers = [];
    renderIdentifiersTable({ identifiers: state.identifiers, identifiersEl });
  }
}

function identifierPayload(row, selectorPrefix) {
  const schemeEl = row.querySelector(`[${selectorPrefix}="scheme"]`);
  const valueEl = row.querySelector(`[${selectorPrefix}="value"]`);
  const sourceEl = row.querySelector(`[${selectorPrefix}="source"]`);
  const primaryEl = row.querySelector(`[${selectorPrefix}="is_primary"]`);
  return {
    scheme: schemeEl && schemeEl.value != null ? String(schemeEl.value).trim() : "",
    value: valueEl && valueEl.value != null ? String(valueEl.value).trim() : "",
    source: sourceEl && sourceEl.value != null ? String(sourceEl.value).trim() : "",
    is_primary: !!(primaryEl && primaryEl.checked),
  };
}

export function bindIdentifierActions({ bookId, identifiersEl, refreshIdentifiers, setError }) {
  identifiersEl.addEventListener("click", async (ev) => {
    const t = ev.target;
    if (!t || !t.getAttribute) return;
    const action = t.getAttribute("data-ident-action");
    if (!action) return;

    const csrf = getCsrfToken();
    if (!csrf) {
      setError("Missing CSRF token cookie. Reload the page and try again.");
      return;
    }

    const row = t.closest ? t.closest("tr") : null;
    if (!row) return;
    const statusSpan = row.querySelector ? row.querySelector("[data-ident-status]") : null;
    const setRowStatus = (text, isError) => setInlineStatus(statusSpan, text, isError);

    if (action === "add") {
      const payload = identifierPayload(row, "data-ident-add-field");
      setRowStatus("Adding...", false);
      try {
        await fetchJSONWithOptions(`/api/v1/library/books/${encodeURIComponent(String(bookId))}/identifiers/`, {
          method: "POST",
          headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": csrf },
          body: JSON.stringify(payload),
        });
        setRowStatus("Added.", false);
        await refreshIdentifiers();
      } catch (e) {
        console.error("Add identifier failed", e);
        setRowStatus("Add failed.", true);
        const msg = extractApiErrorMessage(e);
        const body = e && e.body ? e.body : null;
        const fields = summarizeFieldErrors(body);
        setError(fields ? `${msg} (${fields})` : msg);
      }
      return;
    }

    const identId = row.getAttribute("data-ident-id") || "";
    if (!identId) return;

    if (action === "delete") {
      setRowStatus("Deleting...", false);
      try {
        await fetchJSONWithOptions(
          `/api/v1/library/books/${encodeURIComponent(String(bookId))}/identifiers/${encodeURIComponent(String(identId))}/`,
          { method: "DELETE", headers: { Accept: "application/json", "X-CSRFToken": csrf } }
        );
        setRowStatus("Deleted.", false);
        await refreshIdentifiers();
      } catch (e) {
        console.error("Delete identifier failed", e);
        setRowStatus("Delete failed.", true);
        setError(`Failed to delete identifier: ${extractApiErrorMessage(e)}`);
      }
      return;
    }

    if (action === "save") {
      const payload = identifierPayload(row, "data-ident-field");
      setRowStatus("Saving...", false);
      try {
        await fetchJSONWithOptions(
          `/api/v1/library/books/${encodeURIComponent(String(bookId))}/identifiers/${encodeURIComponent(String(identId))}/`,
          {
            method: "PATCH",
            headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": csrf },
            body: JSON.stringify(payload),
          }
        );
        setRowStatus("Saved.", false);
        await refreshIdentifiers();
      } catch (e) {
        console.error("Save identifier failed", e);
        setRowStatus("Save failed.", true);
        const msg = extractApiErrorMessage(e);
        const body = e && e.body ? e.body : null;
        const fields = summarizeFieldErrors(body);
        setError(fields ? `${msg} (${fields})` : msg);
      }
    }
  });
}
