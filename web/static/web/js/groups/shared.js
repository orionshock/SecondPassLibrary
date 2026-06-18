import { fetchJSON } from "../api.js";
import { escapeHtml } from "../layout.js";
import { shelfMetadataLine } from "../shelves/shared.js";

export function truthy(v) {
  return !!v;
}

export function isManagerOrOwner(me) {
  if (!me) return false;
  return !!me.is_owner || me.role === "manager";
}

export function isLibrarian(me) {
  if (!me) return false;
  return me.role === "librarian";
}

export function canEditGroupPage({ me, group }) {
  if (!me || !group) return false;
  if (isManagerOrOwner(me) || isLibrarian(me)) return true;
  if (group.is_public_group) return false;
  return group.membership_role === "curator";
}

export function canEditGroupDescription({ me, group }) {
  if (!me || !group) return false;
  if (group.is_public_group) return isManagerOrOwner(me) || isLibrarian(me);
  return isManagerOrOwner(me) || isLibrarian(me) || group.membership_role === "curator";
}

export function canManageGroupBooks({ me, group }) {
  if (!me || !group) return false;
  if (isManagerOrOwner(me) || isLibrarian(me)) return true;
  if (group.is_public_group) return false;
  return group.membership_role === "curator";
}

export function canManageGroupMemberships(me) {
  const caps = me && me.capabilities ? me.capabilities : {};
  return !!caps.can_manage_group_memberships;
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
      const ownerBadge = m.is_owner ? ' <span class="pill pill--owner">Owner</span>' : "";
      const username = m.username || "";
      const role = m.role || "reader";
      const email = m.email || "";
      return `
        <article class="book">
          <div style="display:flex; gap: 12px; justify-content: space-between; align-items: baseline; flex-wrap: wrap;">
            <div>
              <h3 class="book__title" style="display:inline;">${escapeHtml(username)}${ownerBadge}</h3>
              <div class="muted">Role: <code>${escapeHtml(role)}</code>${email ? `  -  ${escapeHtml(email)}` : ""}</div>
            </div>
          </div>
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
      const ownerBadge = m.is_owner ? ' <span class="pill pill--owner">Owner</span>' : "";
      const username = m.username || "";
      const role = m.role || "reader";
      const email = m.email || "";
      const curatorDisabled = isPublicGroup ? "disabled" : "";
      const selectDisabled = isPublicGroup ? "disabled" : "";
      const saveDisabled = isPublicGroup ? "disabled" : "";
      const note = isPublicGroup
        ? '<div class="muted">Public is the default/fallback group. Role remains reader; removal is allowed when other memberships remain (final removal restores Public).</div>'
        : "";

      return `
        <article class="book">
          <h3 class="book__title">${escapeHtml(username)}${ownerBadge}</h3>
            <div class="book__meta">
              ${email ? `<div>${escapeHtml(email)}</div>` : ""}
              <div>Role: <select data-action="member-role" data-membership-id="${escapeHtml(m.id)}" ${selectDisabled}>
                <option value="reader" ${role === "reader" ? "selected" : ""}>reader</option>
                <option value="curator" ${role === "curator" ? "selected" : ""} ${curatorDisabled}>curator</option>
              </select></div>
              ${note}
            </div>
            <div style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap;">
              <button class="button" type="button" data-action="member-save" data-membership-id="${escapeHtml(m.id)}" ${saveDisabled}>Save role</button>
              <button class="button" type="button" data-action="member-remove" data-membership-id="${escapeHtml(m.id)}">Remove</button>
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
