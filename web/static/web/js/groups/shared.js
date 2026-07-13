import { fetchJSON } from "../api.js";
import {
  canManageLibrary,
  canManageGroupMemberships as accountCanManageGroupMemberships,
  isManager,
  isOwner,
} from "../auth.js";
import { escapeHtml } from "../layout.js";
import { shelfMetadataLine } from "../shelves/shared.js";
import { renderUserIdentity } from "../ui/identity.js";

export function truthy(v) {
  return !!v;
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

      const actions = [
        id ? `<a class="button" href="${escapeHtml(href)}">View</a>` : "",
        rowCanEdit && id ? `<a class="button" href="${escapeHtml(editHref)}">Edit</a>` : "",
      ]
        .filter(truthy)
        .join(" ");

      return `
        <article class="book">
          <div style="display:flex; gap: 12px; justify-content: space-between; align-items: baseline; flex-wrap: wrap;">
            <div style="flex: 1;">
              <h3 class="book__title"><a href="${escapeHtml(href)}">${escapeHtml(name)}</a></h3>
              ${descSnippet ? `<div class="muted" style="margin-top: 4px;">${escapeHtml(descSnippet)}</div>` : ""}
              ${metaLine ? `<div class="muted" style="margin-top: 4px;">${metaLine}</div>` : ""}
            </div>
            ${actions ? `<div style="display:flex; gap: 10px; align-items: center; flex-wrap: wrap;">${actions}</div>` : ""}
          </div>
        </article>
      `.trim();
    })
    .join("");
}

export function renderBooksCompact(payload, { groupId, canRemove }) {
  const results = Array.isArray(payload && payload.results) ? payload.results : [];
  if (results.length === 0) return "";

  return results
    .map((b) => {
      const title = b.title || "(Untitled)";
      const subtitle = b.subtitle ? ` <span class="muted">- ${escapeHtml(b.subtitle)}</span>` : "";
      const href = b.id ? `/library/books/${encodeURIComponent(String(b.id))}/` : null;
      const authors = Array.isArray(b.authors) ? b.authors.map((a) => a.name).filter(Boolean) : [];
      const coverUrl = b.cover_url ? String(b.cover_url) : "";

      const removeBtn =
        canRemove && b.id && groupId
          ? `<button class="button" type="button" data-action="remove-book" data-book-id="${escapeHtml(
              b.id
            )}">Remove</button>`
          : "";

      return `
        <article class="book book--with-cover">
          <div class="book__cover" data-cover-url="${escapeHtml(coverUrl)}" data-cover-title="${escapeHtml(title)}"></div>
          <div style="display:flex; gap: 12px; justify-content: space-between; align-items: baseline; flex-wrap: wrap;">
            <div>
              <h3 class="book__title" style="display:inline;">
                ${href ? `<a href="${escapeHtml(href)}">${escapeHtml(title)}</a>${subtitle}` : `${escapeHtml(title)}${subtitle}`}
              </h3>
              ${authors.length ? `<div class="muted">${escapeHtml(authors.join(", "))}</div>` : ""}
            </div>
            ${removeBtn ? `<div>${removeBtn}</div>` : ""}
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
      const identity = renderUserIdentity(user, { includeEmail: true }).outerHTML;
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
      const identity = renderUserIdentity(user, { includeEmail: true }).outerHTML;
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

export async function loadAllManageableUsers() {
  const users = [];
  let url = "/api/v1/accounts/users/";
  for (let i = 0; i < 10 && url; i++) {
    const payload = await fetchJSON(url);
    const results = Array.isArray(payload && payload.results) ? payload.results : [];
    for (const u of results) users.push(u);
    url = payload.next || null;
  }
  return users;
}
