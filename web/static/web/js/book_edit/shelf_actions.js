import { extractApiErrorMessage, fetchJSONWithOptions, getCsrfToken } from "../api.js";
import { setStatus as setInlineStatus } from "../ui/status.js";

export function bindShelfActions({ shelvesEl, shelvesStatusEl, refreshShelves }) {
  shelvesEl.addEventListener("click", async (e) => {
    const target = e.target;
    if (!target || target.nodeType !== 1) return;
    if (target.getAttribute("data-action") !== "remove-from-shelf") return;
    const shelfId = target.getAttribute("data-shelf-id");
    const itemId = target.getAttribute("data-item-id");
    if (!shelfId || !itemId) return;

    const ok = window.confirm("Remove this book from this shelf?");
    if (!ok) return;

    setInlineStatus(shelvesStatusEl, "Removing...", false);
    try {
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;
      await fetchJSONWithOptions(
        `/api/v1/shelves/${encodeURIComponent(String(shelfId))}/items/${encodeURIComponent(String(itemId))}/`,
        { method: "DELETE", headers }
      );
      await refreshShelves();
      setInlineStatus(shelvesStatusEl, "", false);
    } catch (e2) {
      console.error("Failed to remove book from shelf", { shelfId, itemId, e2 });
      setInlineStatus(shelvesStatusEl, extractApiErrorMessage(e2) || "Failed to remove.", true);
    }
  });
}
