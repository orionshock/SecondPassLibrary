import { extractApiErrorMessage, fetchJSON } from "../api.js";
import { escapeHtml, setGlobalError } from "../layout.js";
import { mountCovers } from "../ui/covers.js";

export function setStatus(el, text, isError) {
  if (!el) return;
  el.textContent = text || "";
  el.classList.toggle("error", !!isError);
}

export function formatUserDisplayName(user) {
  if (!user) return "";
  const first = user.first_name ? String(user.first_name).trim() : "";
  const last = user.last_name ? String(user.last_name).trim() : "";
  return [first, last].filter(Boolean).join(" ").trim();
}

export function formatUserHandle(user) {
  if (!user || !user.username) return "";
  return `<@${String(user.username).trim()}>`;
}

export function formatUserDisplay(user) {
  const displayName = formatUserDisplayName(user);
  const handle = formatUserHandle(user);
  if (displayName && handle) return `${displayName} ${handle}`;
  if (handle) return handle;
  if (displayName) return displayName;
  return "Unknown user";
}

export function friendlyUserDisplayName(user) {
  return formatUserDisplay(user);
}

export function shelfVisibilityLabel(shelf) {
  const value = shelf && shelf.visibility ? String(shelf.visibility) : "private";
  if (value === "listed") return "Listed";
  if (value === "private") return "Private";
  return value ? `${value.slice(0, 1).toUpperCase()}${value.slice(1)}` : "";
}

export function shelfItemCountLabel(shelf) {
  if (!shelf || shelf.item_count == null) return "";
  const count = Number(shelf.item_count);
  if (!Number.isFinite(count)) return "";
  return `${count} item${count === 1 ? "" : "s"}`;
}

export function shelfOwnerIdentitySegment(shelf) {
  if (!shelf) return "";
  const ownerType = shelf.owner_type ? String(shelf.owner_type) : "";
  if (ownerType === "user") {
    const text = formatUserDisplay(shelf.owner_user);
    return `
      <span class="shelf-owner-identity" data-owner-type="user">
        <span class="material-symbols-outlined" aria-hidden="true">person</span>
        <span>${escapeHtml(text)}</span>
      </span>
    `.trim();
  }
  if (ownerType === "group") {
    const text = shelf.owner_group && shelf.owner_group.name ? String(shelf.owner_group.name) : "Group";
    return `
      <span class="shelf-owner-identity" data-owner-type="group">
        <span class="material-symbols-outlined" aria-hidden="true">groups</span>
        <span>${escapeHtml(text)}</span>
      </span>
    `.trim();
  }
  return "";
}

export function shelfMetadataParts(shelf) {
  if (!shelf) return [];
  const visibility = shelfVisibilityLabel(shelf);
  const itemCount = shelfItemCountLabel(shelf);
  return [visibility, itemCount].filter(Boolean);
}

export function shelfMetadataLine(shelf) {
  const ownerSegment = shelfOwnerIdentitySegment(shelf);
  const metadataSegments = shelfMetadataParts(shelf).map((part) => escapeHtml(part));
  return [ownerSegment, ...metadataSegments]
    .filter(Boolean)
    .join('<span class="shelf-meta-separator" aria-hidden="true"> &middot; </span>');
}

export function shelfOwnerDisplay(shelf, me) {
  if (!shelf) return "";
  const ownerType = shelf.owner_type ? String(shelf.owner_type) : "";
  if (ownerType === "user" && shelf.owner_user) {
    return formatUserDisplay(shelf.owner_user);
  }
  if (ownerType === "group" && shelf.owner_group) {
    const name = shelf.owner_group.name ? String(shelf.owner_group.name) : "group";
    return name;
  }
  return "";
}

export function shelfCreatedByDisplay(shelf) {
  if (!shelf || !shelf.created_by) return "";
  const name = formatUserDisplay(shelf.created_by);
  return name ? `Created by ${name}` : "";
}

export async function pagedController({ statusEl, resultsEl, prevBtn, nextBtn, noteEl, initialUrl, renderRow, emptyText }) {
  let nextUrl = null;
  let prevUrl = null;
  let currentUrl = initialUrl;

  async function load(url) {
    setStatus(statusEl, "Loading...", false);
    const payload = await fetchJSON(url);
    const rows = Array.isArray(payload && payload.results) ? payload.results : [];
    resultsEl.innerHTML = rows.length ? rows.map(renderRow).join("") : `<div class="muted">${escapeHtml(emptyText)}</div>`;
    mountCovers(resultsEl);
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
  if (shelf.owner_type === "user") {
    const ownerProfileId = shelf.owner_user && shelf.owner_user.profile_id != null ? String(shelf.owner_user.profile_id) : "";
    const meProfileId = me.profile_id != null ? String(me.profile_id) : "";
    if (ownerProfileId && meProfileId) return ownerProfileId === meProfileId;
    return shelf.owner_user && String(shelf.owner_user.username) === String(me.username || "");
  }

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
