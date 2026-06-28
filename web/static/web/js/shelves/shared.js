import { escapeHtml } from "../layout.js";
import { renderGroupBadge } from "../ui/groups.js";
import { renderUserIdentity, userIdentityText } from "../ui/identity.js";

function shelfVisibilityLabel(shelf) {
  if (shelf && shelf.owner_type === "group") return "";
  const value = shelf && shelf.visibility ? String(shelf.visibility) : "private";
  if (value === "listed") return "Listed";
  if (value === "private") return "Private";
  return value ? `${value.slice(0, 1).toUpperCase()}${value.slice(1)}` : "";
}

function shelfItemCountLabel(shelf) {
  if (!shelf || shelf.item_count == null) return "";
  const count = Number(shelf.item_count);
  if (!Number.isFinite(count)) return "";
  return `${count} item${count === 1 ? "" : "s"}`;
}

function renderShelfOwnerIdentity(shelf) {
  if (!shelf) return null;
  const ownerType = shelf.owner_type ? String(shelf.owner_type) : "";
  if (ownerType === "user") {
    const identity = renderUserIdentity(shelf.owner_user, {
      className: "shelf-owner-identity",
    });
    identity.dataset.ownerType = "user";
    return identity;
  }
  if (ownerType === "group") {
    const badge = renderGroupBadge(shelf.owner_group, {
      compact: true,
      className: "shelf-owner-identity",
    });
    badge.dataset.ownerType = "group";
    return badge;
  }
  return null;
}

export function shelfOwnerIdentitySegment(shelf) {
  const identity = renderShelfOwnerIdentity(shelf);
  return identity ? identity.outerHTML : "";
}

function shelfMetadataParts(shelf, options = {}) {
  if (!shelf) return [];
  const visibility = shelfVisibilityLabel(shelf);
  const itemCount = shelfItemCountLabel(shelf);
  return [
    options.includeVisibility === false ? "" : visibility,
    options.includeItemCount === false ? "" : itemCount,
  ].filter(Boolean);
}

export function shelfMetadataLine(shelf) {
  const ownerSegment = shelfOwnerIdentitySegment(shelf);
  const metadataSegments = shelfMetadataParts(shelf).map(
    (part) => `<span class="shelf-metadata-piece">${escapeHtml(part)}</span>`
  );
  const wrappedOwner = ownerSegment
    ? `<span class="shelf-metadata-piece">${ownerSegment}</span>`
    : "";
  return [wrappedOwner, ...metadataSegments]
    .filter(Boolean)
    .join("");
}

export function renderShelfMetadata(shelf, options = {}) {
  const container = document.createElement("span");
  container.className = "shelf-metadata";
  const segments = [
    renderShelfOwnerIdentity(shelf),
    ...shelfMetadataParts(shelf, options),
  ].filter(Boolean);

  segments.forEach((segment) => {
    const piece = document.createElement("span");
    piece.className = "shelf-metadata-piece";
    if (typeof segment === "string") {
      piece.textContent = segment;
    } else {
      piece.appendChild(segment);
    }
    container.appendChild(piece);
  });

  return container;
}

export function shelfCreatedByDisplay(shelf) {
  if (!shelf || !shelf.created_by) return "";
  const name = userIdentityText(shelf.created_by);
  return name ? `Created by ${name}` : "";
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

  // For group shelves, use the shelf object's request-scoped edit hint:
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
  return !!(membership && membership.is_curator === true);
}
