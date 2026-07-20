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
              <article class="book card-row--compact">
                <div class="identity-row">
                  <div class="inline-metadata-row identity-row__main">
                    <h3 class="book__title"><a href="${escapeHtml(href)}">${escapeHtml(name)}</a></h3>
                    ${metaLine ? `<span class="muted">${metaLine}</span>` : ""}
                  </div>
                  <div class="badge-row">
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
