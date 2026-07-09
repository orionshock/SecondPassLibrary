import {
  extractApiErrorMessage,
  fetchJSON,
  fetchJSONWithOptions,
  getCsrfToken,
} from "../api.js";
import { escapeHtml, setGlobalError } from "../layout.js";
import { setStatus } from "../ui/status.js";
import { mountCovers } from "../ui/covers.js";

export function initShelfBookSearch({
  shelfId,
  ownerType,
  ownerGroupId,
  searchForm,
  searchInput,
  searchStatus,
  searchResults,
  getCurrentShelfBookIds,
  reloadItems,
}) {
  async function runBookSearch(term) {
    if (!term) {
      searchResults.innerHTML = "";
      return;
    }
    setStatus(searchStatus, "Searching...", false);
    const baseUrl =
      ownerType === "group" && ownerGroupId
        ? `/api/v1/library/groups/${encodeURIComponent(String(ownerGroupId))}/books/`
        : "/api/v1/library/books/";
    const payload = await fetchJSON(`${baseUrl}?q=${encodeURIComponent(term)}`);
    const results = Array.isArray(payload && payload.results) ? payload.results : [];

    if (!results.length) {
      searchResults.innerHTML = `<div class="muted">No results.</div>`;
      setStatus(searchStatus, "", false);
      return;
    }

    const currentShelfBookIds = getCurrentShelfBookIds();
    searchResults.innerHTML = results
      .map((b) => {
        const bid = b.id ? String(b.id) : "";
        const title = b.title ? String(b.title) : "(Untitled)";
        const coverUrl = b.cover_url ? String(b.cover_url) : "";
        const authors = Array.isArray(b.authors) ? b.authors.map((a) => a.name).filter(Boolean) : [];
        const series = b.series && b.series.name ? String(b.series.name) : "";
        const meta = [authors.length ? authors.join(", ") : "", series].filter(Boolean).join("  -  ");
        const inShelf = bid && currentShelfBookIds.has(bid);
        if (inShelf) return "";

        const canAdd = !!bid;
        const addBtn = canAdd
          ? `<button class="button" type="button" data-action="add-book" data-book-id="${escapeHtml(bid)}">Add</button>`
          : "";
        return `
          <article class="book book--with-cover">
            <div class="book__cover" data-cover-url="${escapeHtml(coverUrl)}" data-cover-title="${escapeHtml(title)}"></div>
            <div style="display:flex; gap: 12px; justify-content: space-between; align-items: baseline; flex-wrap: wrap;">
              <div style="flex: 1;">
                <h3 class="book__title">${escapeHtml(title)}</h3>
                ${meta ? `<div class="muted" style="margin-top: 4px;">${escapeHtml(meta)}</div>` : ""}
              </div>
              <div>
                ${addBtn}
              </div>
            </div>
          </article>
        `.trim();
      })
      .filter(Boolean)
      .join("");

    setStatus(searchStatus, "", false);
    mountCovers(searchResults);
  }

  searchForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    setGlobalError("");
    try {
      await runBookSearch(searchInput.value || "");
    } catch (e2) {
      console.error("Search failed", e2);
      setGlobalError(extractApiErrorMessage(e2));
    }
  });

  searchResults.addEventListener("click", async (e) => {
    const target = e.target;
    if (!target || target.nodeType !== 1) return;
    const action = target.getAttribute("data-action");
    const bookId = target.getAttribute("data-book-id");
    if (action !== "add-book" || !bookId) return;

    setGlobalError("");
    setStatus(searchStatus, "Adding...", false);
    try {
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json", "Content-Type": "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;
      await fetchJSONWithOptions(`/api/v1/shelves/${encodeURIComponent(String(shelfId))}/items/`, {
        method: "POST",
        headers,
        body: JSON.stringify({ book: bookId }),
      });
      setStatus(searchStatus, "Added.", false);
      await reloadItems();
      await runBookSearch(searchInput.value || "");
      window.setTimeout(() => setStatus(searchStatus, "", false), 900);
    } catch (e2) {
      console.error("Failed to add book to shelf", e2);
      setGlobalError(extractApiErrorMessage(e2));
      setStatus(searchStatus, "", true);
    }
  });
}
