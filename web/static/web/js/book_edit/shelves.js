import { escapeHtml } from "../layout.js";
import { shelfMetadataLine } from "../shelves/shared.js";
import { setStatus } from "../ui/status.js";

export async function refreshShelvesContext({
  bookId,
  fetchJSON,
  shelvesStatusEl,
  shelvesEl,
}) {
  setStatus(shelvesStatusEl, "Loading...", false);
  try {
    const payload = await fetchJSON(`/api/v1/shelves/?book=${encodeURIComponent(String(bookId))}`);
    const results = payload && Array.isArray(payload.results) ? payload.results : [];
    if (!results.length) {
      shelvesEl.innerHTML = `<div class="muted">No visible shelves contain this book.</div>`;
    } else {
      shelvesEl.innerHTML = results
        .map((s) => {
          const sid = s && s.id != null ? String(s.id) : "";
          const name = s && s.name ? String(s.name) : "(Shelf)";
          const href = sid ? `/shelves/${encodeURIComponent(sid)}/` : "#";
          const editHref = sid ? `/shelves/${encodeURIComponent(sid)}/edit/` : "#";
          const canEdit = s && s.can_edit != null ? !!s.can_edit : false;
          const matchedItemId = s && s.matched_item_id ? String(s.matched_item_id) : "";

          const metaLine = shelfMetadataLine(s);
          const removeBtn =
            canEdit && sid && matchedItemId
              ? `<button class="button" type="button" data-action="remove-from-shelf" data-shelf-id="${escapeHtml(
                  sid
                )}" data-item-id="${escapeHtml(matchedItemId)}">Remove from this shelf</button>`
              : "";

          const actions = [
            `<a class="button" href="${escapeHtml(href)}">View</a>`,
            canEdit ? `<a class="button" href="${escapeHtml(editHref)}">Edit</a>` : "",
            removeBtn,
          ]
            .filter((x) => x && x !== "")
            .join(" ");

          return `
              <article class="book">
                <div style="display:flex; gap: 12px; justify-content: space-between; align-items: baseline; flex-wrap: wrap;">
                  <div style="flex: 1;">
                    <h3 class="book__title"><a href="${escapeHtml(href)}">${escapeHtml(name)}</a></h3>
                    ${metaLine ? `<div class="muted" style="margin-top: 4px;">${metaLine}</div>` : ""}
                  </div>
                  <div style="display:flex; gap: 10px; align-items: center; flex-wrap: wrap;">
                    ${actions}
                  </div>
                </div>
              </article>
            `.trim();
        })
        .join("");
    }
    setStatus(shelvesStatusEl, "", false);
  } catch (e) {
    console.error("Failed to load shelves for book", e);
    setStatus(shelvesStatusEl, "Failed to load shelves.", true);
    shelvesEl.innerHTML = "";
  }
}
