import { extractApiErrorMessage, fetchJSON } from "../api.js";
import { escapeHtml, setGlobalError } from "../layout.js";

export function setStatus(el, text, isError) {
  if (!el) return;
  el.textContent = text || "";
  el.classList.toggle("error", !!isError);
}

export async function pagedController({ statusEl, resultsEl, prevBtn, nextBtn, noteEl, initialUrl, renderRow, emptyText }) {
  let nextUrl = null;
  let prevUrl = null;
  let currentUrl = initialUrl;

  async function load(url) {
    setStatus(statusEl, "Loadingâ€¦", false);
    const payload = await fetchJSON(url);
    const rows = Array.isArray(payload && payload.results) ? payload.results : [];
    resultsEl.innerHTML = rows.length ? rows.map(renderRow).join("") : `<div class="muted">${escapeHtml(emptyText)}</div>`;
    nextUrl = payload && payload.next ? String(payload.next) : null;
    prevUrl = payload && payload.previous ? String(payload.previous) : null;
    currentUrl = url;

    if (prevBtn) prevBtn.disabled = !prevUrl;
    if (nextBtn) nextBtn.disabled = !nextUrl;
    if (noteEl) {
      const count = payload && payload.count != null ? Number(payload.count) : null;
      noteEl.textContent = count != null ? `${count} total` : "";
    }

    setStatus(statusEl, "", false);
    return payload;
  }

  if (prevBtn) {
    prevBtn.addEventListener("click", () => {
      if (!prevUrl) return;
      load(prevUrl).catch((e) => {
        console.error("Pagination prev failed", e);
        setGlobalError(extractApiErrorMessage(e));
      });
    });
  }
  if (nextBtn) {
    nextBtn.addEventListener("click", () => {
      if (!nextUrl) return;
      load(nextUrl).catch((e) => {
        console.error("Pagination next failed", e);
        setGlobalError(extractApiErrorMessage(e));
      });
    });
  }

  return { loadFirst: () => load(initialUrl), reload: () => load(currentUrl) };
}

export function inferCanEditShelf({ me, shelf }) {
  if (!me || !shelf) return false;
  if (shelf.can_edit != null) return !!shelf.can_edit;
  if (shelf.owner_type === "user") return shelf.owner_user && String(shelf.owner_user.username) === String(me.username || "");

  // For group shelves, infer from role/capabilities:
  // - broad roles (owner/manager/librarian) can edit
  // - curator can edit non-Public group shelves if they are curator in that group
  const isOwner = !!me.is_owner;
  const role = me.role || "";
  const isBroad = isOwner || role === "manager" || role === "librarian";
  if (isBroad) return true;

  const og = shelf.owner_group;
  if (!og || og.is_public_group) return false;
  const groups = Array.isArray(me.groups) ? me.groups : [];
  const membership = groups.find((g) => g && String(g.id) === String(og.id));
  return membership && membership.membership_role === "curator";
}

