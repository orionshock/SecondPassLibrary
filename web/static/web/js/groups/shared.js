import {
  canManageLibrary,
  canManageGroupMemberships as accountCanManageGroupMemberships,
  isManager,
  isOwner,
} from "../auth.js";
import { extractApiErrorMessage, summarizeFieldErrors } from "../api.js";
import { escapeHtml } from "../layout.js";
import { shelfMetadataLine } from "../shelves/shared.js";
import { renderCoverPreviewStrip } from "../ui/cover_previews.js";
import { renderUserIdentity } from "../ui/identity.js";
import { renderBookMetadataHtml } from "../ui/book_metadata.js";

export function truthy(v) {
  return !!v;
}

const GROUP_MUTATION_ERROR_MAX_LENGTH = 240;

function boundedGroupErrorText(value) {
  const text = String(value == null ? "" : value).replace(/\s+/g, " ").trim();
  if (!text) return "";
  if (/<!doctype\b/i.test(text) || /<\s*\/?\s*[a-z][^>]*>/i.test(text)) return "";
  if (/\bTraceback \(most recent call last\):/i.test(text)) return "";
  if (/\bFile "[^"]+", line \d+/i.test(text)) return "";
  if (text.length <= GROUP_MUTATION_ERROR_MAX_LENGTH) return text;
  return `${text.slice(0, GROUP_MUTATION_ERROR_MAX_LENGTH - 3)}...`;
}

export function groupMutationErrorMessage(error, fallback) {
  const safeFallback = boundedGroupErrorText(fallback) || "Group operation failed.";
  const body = error && error.body && typeof error.body === "object" && !Array.isArray(error.body)
    ? error.body
    : null;

  if (body) {
    const fieldMessage = boundedGroupErrorText(summarizeFieldErrors(body));
    if (fieldMessage) return fieldMessage;

    const hasStructuredMessage =
      (body.error && typeof body.error === "object") ||
      Object.prototype.hasOwnProperty.call(body, "detail");
    if (hasStructuredMessage) {
      const structuredMessage = boundedGroupErrorText(extractApiErrorMessage(error));
      if (structuredMessage) return structuredMessage;
    }
  }

  const status = error && Number.isFinite(Number(error.status))
    ? Number(error.status)
    : null;
  return boundedGroupErrorText(
    status ? `${safeFallback} (HTTP ${status}).` : safeFallback
  );
}

export function isManagerOrOwner(me) {
  return isOwner(me) || isManager(me);
}

export function currentUserGroupMembership({ me, group }) {
  if (!me || !group || group.id == null) return null;
  const memberships = Array.isArray(me.groups) ? me.groups : [];
  return (
    memberships.find(
      (membership) =>
        membership && membership.id != null && String(membership.id) === String(group.id)
    ) || null
  );
}

export function canCurateGroup({ me, group }) {
  if (!me || !group) return false;
  if (canManageLibrary(me)) return true;
  if (group.is_public_group === true) return false;
  const membership = currentUserGroupMembership({ me, group });
  return !!(membership && membership.is_curator === true);
}

export function canEditGroupPage({ me, group }) {
  return canCurateGroup({ me, group });
}

export function canEditGroupDescription({ me, group }) {
  return canCurateGroup({ me, group });
}

export function canManageGroupBooks({ me, group }) {
  return canCurateGroup({ me, group });
}

export function canManageGroupMemberships(me) {
  return accountCanManageGroupMemberships(me);
}

export function renderGroupShelvesCompact(payload, { canEdit }) {
  const results = Array.isArray(payload && payload.results) ? payload.results : [];
  if (results.length === 0) return "";

  return results
    .map((s) => {
      const id = s && s.id != null ? String(s.id) : "";
      const name = s && s.name ? String(s.name) : "(Unnamed shelf)";
      const desc = s && s.description ? String(s.description) : "";
      const href = id ? `/shelves/${encodeURIComponent(id)}/` : "#";
      const editHref = id ? `/shelves/${encodeURIComponent(id)}/edit/` : "#";
      const rowCanEdit = s && s.can_edit != null ? !!s.can_edit : !!canEdit;

      const descSnippet = desc && desc.length > 160 ? `${desc.slice(0, 160)}...` : desc;
      const metaLine = shelfMetadataLine(s);
      const previews = renderCoverPreviewStrip(s && s.preview_books, {
        href,
        actionLabel: `View shelf ${name}`,
      });

      const actions = [
        id ? `<a class="icon-button" href="${escapeHtml(href)}" aria-label="View shelf ${escapeHtml(name)}" title="View shelf"><span class="material-symbols-outlined" aria-hidden="true">visibility</span></a>` : "",
        rowCanEdit && id ? `<a class="icon-button" href="${escapeHtml(editHref)}" aria-label="Edit shelf ${escapeHtml(name)}" title="Edit shelf"><span class="material-symbols-outlined" aria-hidden="true">edit</span></a>` : "",
      ]
        .filter(truthy)
        .join(" ");

      return `
        <article class="book shelf-list-card group-edit-shelf-card">
          <div class="shelf-list-card__main">
            <h3 class="book__title shelf-list-card__title"><a href="${escapeHtml(href)}">${escapeHtml(name)}</a></h3>
            ${descSnippet ? `<div class="muted shelf-list-card__description">${escapeHtml(descSnippet)}</div>` : ""}
            ${metaLine ? `<div class="muted shelf-list-card__metadata">${metaLine}</div>` : ""}
          </div>
          ${previews}
          ${actions ? `<div class="group-edit-shelf-card__actions">${actions}</div>` : ""}
        </article>
      `.trim();
    })
    .join("");
}

export function renderBooksCompact(payload, { groupId, canRemove, canAdd = false }) {
  const results = Array.isArray(payload && payload.results) ? payload.results : [];
  if (results.length === 0) return "";

  return results
    .map((b) => {
      const title = b.title || "(Untitled)";
      const subtitle = b.subtitle ? String(b.subtitle).trim() : "";
      const href = b.id ? `/library/books/${encodeURIComponent(String(b.id))}/` : null;
      const coverUrl = b.cover_url ? String(b.cover_url) : "";
      const metadata = renderBookMetadataHtml(b, { emptyText: "No metadata." });

      const removeBtn =
        canRemove && b.id && groupId
          ? `<button class="button" type="button" data-action="remove-book" data-book-id="${escapeHtml(
              b.id
            )}">Remove</button>`
          : "";
      const addBtn = canAdd && b.id
        ? `<button class="button" type="button" data-action="add-book" data-book-id="${escapeHtml(b.id)}">Add</button>`
        : "";
      const action = removeBtn || addBtn;

      return `
        <article class="library-row group-edit-book-row">
          <div class="book__cover" data-cover-url="${escapeHtml(coverUrl)}" data-cover-title="${escapeHtml(title)}"></div>
          <div class="library-row__body group-edit-book-row__body">
            <div class="group-edit-book-row__content">
              <h3 class="library-row__title">
                ${href ? `<a href="${escapeHtml(href)}">${escapeHtml(title)}</a>` : escapeHtml(title)}
              </h3>
              ${subtitle ? `<div class="library-row__subtitle">${escapeHtml(subtitle)}</div>` : ""}
              <div class="library-row__meta book-metadata">${metadata}</div>
            </div>
            ${action ? `<div class="group-edit-book-row__action">${action}</div>` : ""}
          </div>
        </article>
      `.trim();
    })
    .join("");
}

export function renderMembersReadOnly(payload) {
  const results = Array.isArray(payload && payload.results) ? payload.results : [];
  if (results.length === 0) return "";

  return results
    .map((m) => {
      const user = m && m.user ? m.user : m;
      const identity = renderUserIdentity(user, { includeDisplayName: false }).outerHTML;
      const curator = m && m.is_curator ? ' <span class="muted">(Curator)</span>' : "";
      return `
        <article class="membership-row membership-row--readonly">
          <div class="membership-row__group membership-row__identity">${identity}${curator}</div>
        </article>
      `.trim();
    })
    .join("");
}

export function renderMembersManage(payload, { isPublicGroup }) {
  const results = Array.isArray(payload && payload.results) ? payload.results : [];
  if (results.length === 0) return "";

  return results
    .map((m) => {
      const user = m && m.user ? m.user : m;
      const userId = user && user.profile_id ? String(user.profile_id) : "";
      const isCurator = !!m.is_curator;
      const identity = renderUserIdentity(user, { includeDisplayName: false }).outerHTML;
      const note = isPublicGroup
        ? '<div class="membership-row__note muted">Public fallback group; curator unavailable.</div>'
        : "";
      const curatorControl = isPublicGroup
        ? ""
        : `
              <label class="membership-row__curator">
                <input type="checkbox" data-action="member-curator" data-user-id="${escapeHtml(userId)}" ${isCurator ? "checked" : ""} />
                <span>Curator</span>
              </label>
            `.trim();

      return `
        <article class="membership-row">
          <div class="membership-row__actions">
            <button class="icon-button icon-button--danger" type="button" data-action="member-remove" data-user-id="${escapeHtml(userId)}" aria-label="Remove member" title="Remove member"><span class="material-symbols-outlined" aria-hidden="true">remove_circle</span></button>
          </div>
          <div class="membership-row__group membership-row__identity">${identity}</div>
          <div class="membership-row__controls">
            ${curatorControl}
            ${note}
            <span class="membership-row__status muted" aria-live="polite"></span>
          </div>
        </article>
        `.trim();
    })
    .join("");
}
