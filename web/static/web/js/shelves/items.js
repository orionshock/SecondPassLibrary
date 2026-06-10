import {
  extractApiErrorMessage,
  fetchJSON,
  fetchJSONWithOptions,
  getCsrfToken,
} from "../api.js";
import { escapeHtml, setGlobalError } from "../layout.js";
import { setStatus } from "./shared.js";
import { mountCovers } from "../ui/covers.js";

export async function initShelfItemsEditor({
  shelfId,
  itemsStatus,
  itemsResults,
  prevBtn,
  nextBtn,
  noteEl,
  itemCountEl,
}) {
  let currentItems = [];
  let currentItemTotal = 0;

  async function loadItems(url) {
    setStatus(itemsStatus, "Loading...", false);
    const payload = await fetchJSON(url);
    const results = Array.isArray(payload && payload.results) ? payload.results : [];
    const totalCount = Number(payload && payload.count);
    const itemTotal = Number.isFinite(totalCount) ? totalCount : results.length;
    currentItems = results;
    currentItemTotal = itemTotal;
    if (!results.length) itemsResults.innerHTML = `<div class="muted">No books.</div>`;
    else {
      itemsResults.innerHTML = results
        .map((it) => {
          const b = it.book || {};
          const bid = b.id ? String(b.id) : "";
          const title = b.title ? String(b.title) : "(Untitled)";
          const coverUrl = b.cover_url ? String(b.cover_url) : "";
          const authors = Array.isArray(b.authors) ? b.authors.map((a) => a.name).filter(Boolean) : [];
          const series = b.series && b.series.name ? String(b.series.name) : "";
          const meta = [authors.length ? authors.join(", ") : "", series].filter(Boolean).join("  -  ");
          const storedPosition = Number(it.position);
          const hasPosition = Number.isFinite(storedPosition);
          const displayPosition = hasPosition ? storedPosition + 1 : "";
          const canMoveUp = hasPosition && storedPosition > 0;
          const canMoveDown = hasPosition && storedPosition < itemTotal - 1;
          const moveOptions = Array.from({ length: itemTotal }, (_unused, idx) => {
            const selected = hasPosition && idx === storedPosition ? " selected disabled" : "";
            return `<option value="${idx}"${selected}>#${idx + 1}</option>`;
          }).join("");
          return `
            <article class="book book--with-cover">
              <div class="book__cover" data-cover-url="${escapeHtml(coverUrl)}" data-cover-title="${escapeHtml(title)}"></div>
              <div style="display:flex; gap: 12px; justify-content: space-between; align-items: baseline; flex-wrap: wrap;">
                <div style="flex: 1;">
                  <h3 class="book__title">
                    <a href="/library/books/${encodeURIComponent(bid)}/">${escapeHtml(title)}</a>
                  </h3>
                  ${meta ? `<div class="muted" style="margin-top: 4px;">${escapeHtml(meta)}</div>` : ""}
                  <div class="muted" style="margin-top: 6px; display:flex; gap: 10px; align-items:center; flex-wrap: wrap;">
                    <span class="muted">#${escapeHtml(displayPosition)}</span>
                    <button class="button" type="button" data-action="move-up" data-item-id="${escapeHtml(it.id)}"${canMoveUp ? "" : " disabled"}>Move up</button>
                    <button class="button" type="button" data-action="move-down" data-item-id="${escapeHtml(it.id)}"${canMoveDown ? "" : " disabled"}>Move down</button>
                    <label>
                      <span class="muted">Move to</span>
                      <select data-action="move-to" data-item-id="${escapeHtml(it.id)}" data-current-position="${escapeHtml(hasPosition ? storedPosition : "")}" aria-label="Move ${escapeHtml(title)} to position">
                        ${moveOptions}
                      </select>
                    </label>
                    <button class="button" type="button" data-action="remove-item" data-item-id="${escapeHtml(it.id)}">Remove</button>
                  </div>
                </div>
              </div>
            </article>
          `.trim();
        })
        .join("");
    }
    prevBtn.disabled = !payload.previous;
    nextBtn.disabled = !payload.next;
    noteEl.textContent = payload.count != null ? `${payload.count} total` : "";
    itemCountEl.textContent = payload.count != null ? `Items: ${payload.count}` : "";
    setStatus(itemsStatus, "", false);
    mountCovers(itemsResults);
    return payload;
  }

  let itemsNext = null;
  let itemsPrev = null;
  let currentItemsUrl = `/api/v1/shelves/${encodeURIComponent(String(shelfId))}/items/`;
  let currentShelfBookIds = new Set();

  async function refreshAllShelfBookIds() {
    const ids = new Set();
    let url = `/api/v1/shelves/${encodeURIComponent(String(shelfId))}/items/?page_size=200`;
    let guard = 0;
    while (url && guard < 20) {
      guard += 1;
      const payload = await fetchJSON(url);
      const results = Array.isArray(payload && payload.results) ? payload.results : [];
      for (const it of results) {
        const b = it && it.book ? it.book : null;
        if (b && b.id != null) ids.add(String(b.id));
      }
      url = payload && payload.next ? String(payload.next) : "";
    }
    currentShelfBookIds = ids;
  }

  async function reloadItems() {
    const payload = await loadItems(currentItemsUrl);
    itemsNext = payload.next ? String(payload.next) : null;
    itemsPrev = payload.previous ? String(payload.previous) : null;
    await refreshAllShelfBookIds();
  }

  prevBtn.addEventListener("click", () => {
    if (!itemsPrev) return;
    currentItemsUrl = itemsPrev;
    reloadItems().catch((e) => setGlobalError(extractApiErrorMessage(e)));
  });
  nextBtn.addEventListener("click", () => {
    if (!itemsNext) return;
    currentItemsUrl = itemsNext;
    reloadItems().catch((e) => setGlobalError(extractApiErrorMessage(e)));
  });

  async function patchShelfItemMove(itemId, move) {
    const csrf = getCsrfToken();
    const headers = { Accept: "application/json", "Content-Type": "application/json" };
    if (csrf) headers["X-CSRFToken"] = csrf;
    await fetchJSONWithOptions(
      `/api/v1/shelves/${encodeURIComponent(String(shelfId))}/items/${encodeURIComponent(String(itemId))}/`,
      { method: "PATCH", headers, body: JSON.stringify({ move }) }
    );
  }

  async function patchShelfItemPosition(itemId, position) {
    const csrf = getCsrfToken();
    const headers = { Accept: "application/json", "Content-Type": "application/json" };
    if (csrf) headers["X-CSRFToken"] = csrf;
    await fetchJSONWithOptions(
      `/api/v1/shelves/${encodeURIComponent(String(shelfId))}/items/${encodeURIComponent(String(itemId))}/`,
      { method: "PATCH", headers, body: JSON.stringify({ position }) }
    );
  }

  itemsResults.addEventListener("click", async (e) => {
    const target = e.target;
    if (!target || target.nodeType !== 1) return;
    const action = target.getAttribute("data-action");
    const itemId = target.getAttribute("data-item-id");
    if (!action || !itemId) return;

    if (action === "remove-item") {
      setGlobalError("");
      setStatus(itemsStatus, "Removing...", false);
      try {
        const csrf = getCsrfToken();
        const headers = { Accept: "application/json" };
        if (csrf) headers["X-CSRFToken"] = csrf;
        await fetchJSONWithOptions(
          `/api/v1/shelves/${encodeURIComponent(String(shelfId))}/items/${encodeURIComponent(String(itemId))}/`,
          { method: "DELETE", headers }
        );
        await reloadItems();
      } catch (e2) {
        console.error("Failed to remove shelf item", e2);
        setGlobalError(extractApiErrorMessage(e2));
        setStatus(itemsStatus, "", true);
      }
    }

    if (action === "move-up" || action === "move-down") {
      const idx = currentItems.findIndex((it) => it && String(it.id) === String(itemId));
      if (idx < 0) return;
      const item = currentItems[idx];
      const storedPosition = Number(item && item.position);
      if (!Number.isFinite(storedPosition)) return;
      if (action === "move-up" && storedPosition <= 0) return;
      if (action === "move-down" && storedPosition >= currentItemTotal - 1) return;

      setGlobalError("");
      setStatus(itemsStatus, "Reordering...", false);
      try {
        await patchShelfItemMove(itemId, action === "move-up" ? "up" : "down");
        await reloadItems();
      } catch (e2) {
        console.error("Failed to reorder shelf items", e2);
        setGlobalError(extractApiErrorMessage(e2));
        setStatus(itemsStatus, "", true);
      }
    }
  });

  itemsResults.addEventListener("change", async (e) => {
    const target = e.target;
    if (!target || target.nodeType !== 1) return;
    const action = target.getAttribute("data-action");
    const itemId = target.getAttribute("data-item-id");
    if (action !== "move-to" || !itemId) return;

    const nextPosition = Number(target.value);
    const currentPosition = Number(target.getAttribute("data-current-position"));
    if (!Number.isFinite(nextPosition)) return;
    if (Number.isFinite(currentPosition) && nextPosition === currentPosition) return;

    setGlobalError("");
    setStatus(itemsStatus, "Reordering...", false);
    target.disabled = true;
    try {
      await patchShelfItemPosition(itemId, nextPosition);
      await reloadItems();
    } catch (e2) {
      console.error("Failed to move shelf item", e2);
      setGlobalError(extractApiErrorMessage(e2));
      setStatus(itemsStatus, "", true);
      target.disabled = false;
    }
  });

  await reloadItems();

  return {
    reloadItems,
    getCurrentShelfBookIds: () => currentShelfBookIds,
  };
}
