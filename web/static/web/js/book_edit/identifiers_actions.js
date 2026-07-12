import {
  fetchJSON,
  fetchJSONWithOptions,
  getCsrfToken,
  summarizeFieldErrors,
} from "../api.js";
import { renderIdentifiersTable } from "./identifiers_file.js";
import { setStatus } from "../ui/status.js";

export async function refreshIdentifiersContext({
  bookId,
  identifiersStatusEl,
  identifiersEl,
  state,
  setError,
}) {
  setStatus(identifiersStatusEl, "Loading...", false);
  try {
    const list = await fetchJSON(`/api/v1/library/books/${encodeURIComponent(String(bookId))}/identifiers/`);
    state.identifiers = Array.isArray(list) ? list : [];
    setStatus(identifiersStatusEl, "", false);
    renderIdentifiersTable({ identifiers: state.identifiers, identifiersEl });
  } catch (e) {
    setStatus(identifiersStatusEl, "Failed to load.", true);
    setError("Failed to load identifiers. Reload the page and try again.");
    state.identifiers = [];
    renderIdentifiersTable({ identifiers: state.identifiers, identifiersEl });
  }
}

function identifierPayload(row, selectorPrefix) {
  const schemeEl = row.querySelector(`[${selectorPrefix}="scheme"]`);
  const valueEl = row.querySelector(`[${selectorPrefix}="value"]`);
  return {
    scheme: schemeEl && schemeEl.value != null ? String(schemeEl.value).trim() : "",
    value: valueEl && valueEl.value != null ? String(valueEl.value).trim() : "",
  };
}

function safeIdentifierError(error, fallback) {
  const body = error && error.body && typeof error.body === "object" ? error.body : null;
  const fields = summarizeFieldErrors(body);
  if (fields) return `${fallback} (${fields})`;
  if (body && body.detail) return String(body.detail).slice(0, 240);
  return fallback;
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
    const setRowStatus = (text, isError) => setStatus(statusSpan, text, isError);

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
        setRowStatus("Add failed.", true);
        setError(safeIdentifierError(e, "Failed to add identifier."));
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
        setRowStatus("Delete failed.", true);
        setError(safeIdentifierError(e, "Failed to delete identifier."));
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
        setRowStatus("Save failed.", true);
        setError(safeIdentifierError(e, "Failed to save identifier."));
      }
    }
  });
}
