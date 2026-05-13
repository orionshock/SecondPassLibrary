import {
  fetchJSON,
  fetchJSONWithOptions,
  getCsrfToken,
  extractApiErrorMessage,
  summarizeFieldErrors,
} from "./api.js";
import { $, escapeHtml, formatRole, loadMeAndInitShell, setGlobalError, visible } from "./layout.js";

function truthy(v) {
  return !!v;
}

function isManagerOrOwner(me) {
  if (!me) return false;
  return !!me.is_owner || me.role === "manager";
}

function isLibrarian(me) {
  if (!me) return false;
  return me.role === "librarian";
}

function canEditGroupPage({ me, group }) {
  if (!me || !group) return false;
  if (isManagerOrOwner(me) || isLibrarian(me)) return true;
  if (group.is_public_group) return false;
  return group.membership_role === "curator";
}

function canEditGroupDescription({ me, group }) {
  if (!me || !group) return false;
  if (group.is_public_group) return isManagerOrOwner(me) || isLibrarian(me);
  return isManagerOrOwner(me) || isLibrarian(me) || group.membership_role === "curator";
}

function canManageGroupBooks({ me, group }) {
  if (!me || !group) return false;
  if (isManagerOrOwner(me) || isLibrarian(me)) return true;
  if (group.is_public_group) return false;
  return group.membership_role === "curator";
}

function canManageGroupMemberships(me) {
  const caps = me && me.capabilities ? me.capabilities : {};
  return !!caps.can_manage_group_memberships;
}

function initTabs(root) {
  if (!root) return;
  const buttons = Array.from(root.querySelectorAll("[data-tab]"));
  const panels = Array.from(root.querySelectorAll("[data-tab-panel]"));
  if (!buttons.length || !panels.length) return;

  function setActive(key) {
    for (const b of buttons) b.classList.toggle("is-active", b.getAttribute("data-tab") === key);
    for (const p of panels) p.classList.toggle("is-hidden", p.getAttribute("data-tab-panel") !== key);
  }

  for (const b of buttons) {
    b.addEventListener("click", () => {
      const key = b.getAttribute("data-tab") || "";
      if (key) setActive(key);
    });
  }
}

function renderGroupsList(payload) {
  const results = Array.isArray(payload && payload.results) ? payload.results : [];
  if (results.length === 0) return "";

  return results
    .map((g) => {
      const name = g.name || "";
      const membershipRole = g.membership_role || "";
      const isPublic = !!g.is_public_group;
      const href = g.id ? `/groups/${encodeURIComponent(String(g.id))}/` : "#";

      const badgeBits = [
        isPublic ? '<span class="pill pill--owner">Public</span>' : "",
        membershipRole ? `<span class="pill">Your role: ${escapeHtml(membershipRole)}</span>` : "",
      ].filter(truthy);

      const badges = badgeBits.length ? `<span class="edit-header__badges">${badgeBits.join(" ")}</span>` : "";

      return `
        <article class="book">
          <div style="display:flex; gap: 12px; justify-content: space-between; align-items: baseline; flex-wrap: wrap;">
            <div>
              <h3 class="book__title" style="display:inline;">
                <a href="${escapeHtml(href)}">${escapeHtml(name)}</a>
              </h3>
              ${badges ? ` <span style="margin-left: 8px;">${badges}</span>` : ""}
            </div>
          </div>
        </article>
      `.trim();
    })
    .join("");
}

function renderGroupShelvesCompact(payload, { canEdit }) {
  const results = Array.isArray(payload && payload.results) ? payload.results : [];
  if (results.length === 0) return "";

  return results
    .map((s) => {
      const id = s && s.id != null ? String(s.id) : "";
      const name = s && s.name ? String(s.name) : "(Unnamed shelf)";
      const desc = s && s.description ? String(s.description) : "";
      const itemCount = s && s.item_count != null ? Number(s.item_count) : null;
      const href = id ? `/shelves/${encodeURIComponent(id)}/` : "#";
      const editHref = id ? `/shelves/${encodeURIComponent(id)}/edit/` : "#";

      const descSnippet = desc && desc.length > 160 ? `${desc.slice(0, 160)}…` : desc;
      const countLine = itemCount != null ? `${itemCount} item${itemCount === 1 ? "" : "s"}` : "";

      const actions = [
        id ? `<a class="button" href="${escapeHtml(href)}">View</a>` : "",
        canEdit && id ? `<a class="button" href="${escapeHtml(editHref)}">Edit</a>` : "",
      ]
        .filter(truthy)
        .join(" ");

      return `
        <article class="book">
          <div style="display:flex; gap: 12px; justify-content: space-between; align-items: baseline; flex-wrap: wrap;">
            <div style="flex: 1;">
              <h3 class="book__title"><a href="${escapeHtml(href)}">${escapeHtml(name)}</a></h3>
              ${descSnippet ? `<div class="muted" style="margin-top: 4px;">${escapeHtml(descSnippet)}</div>` : ""}
              ${countLine ? `<div class="muted" style="margin-top: 4px;">${escapeHtml(countLine)}</div>` : ""}
            </div>
            ${actions ? `<div style="display:flex; gap: 10px; align-items: center; flex-wrap: wrap;">${actions}</div>` : ""}
          </div>
        </article>
      `.trim();
    })
    .join("");
}

function renderBooksCompact(payload, { groupId, canRemove }) {
  const results = Array.isArray(payload && payload.results) ? payload.results : [];
  if (results.length === 0) return "";

  return results
    .map((b) => {
      const title = b.title || "(Untitled)";
      const subtitle = b.subtitle ? ` <span class="muted">— ${escapeHtml(b.subtitle)}</span>` : "";
      const href = b.id ? `/library/books/${encodeURIComponent(String(b.id))}/` : null;
      const authors = Array.isArray(b.authors) ? b.authors.map((a) => a.name).filter(Boolean) : [];

      const removeBtn =
        canRemove && b.id && groupId
          ? `<button class="button" type="button" data-action="remove-book" data-book-id="${escapeHtml(
              b.id
            )}">Remove</button>`
          : "";

      return `
        <article class="book">
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

function renderMembersReadOnly(payload) {
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
              <div class="muted">Role: <code>${escapeHtml(role)}</code>${email ? ` · ${escapeHtml(email)}` : ""}</div>
            </div>
          </div>
        </article>
      `.trim();
    })
    .join("");
}

function renderMembersManage(payload, { isPublicGroup }) {
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

async function loadAllManageableUsers() {
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

function setStatus(el, text, isError) {
  if (!el) return;
  el.textContent = text || "";
  el.classList.toggle("error", !!isError);
}

async function pagedListController({
  statusEl,
  resultsEl,
  nextBtn,
  prevBtn,
  initialUrl,
  emptyText,
  render,
}) {
  let nextUrl = null;
  let prevUrl = null;

  async function load(url) {
    setStatus(statusEl, "Loading…", false);
    resultsEl.innerHTML = "";
    nextBtn.disabled = true;
    prevBtn.disabled = true;

    try {
      const payload = await fetchJSON(url);
      const results = Array.isArray(payload && payload.results) ? payload.results : [];
      if (results.length === 0) {
        setStatus(statusEl, emptyText, false);
        nextUrl = null;
        prevUrl = null;
        return;
      }

      setStatus(
        statusEl,
        payload && payload.count != null ? `Showing ${results.length} of ${payload.count}.` : "",
        false
      );
      resultsEl.innerHTML = render(payload);

      nextUrl = payload.next || null;
      prevUrl = payload.previous || null;
      nextBtn.disabled = !nextUrl;
      prevBtn.disabled = !prevUrl;
    } catch (e) {
      console.error("Failed to load list", { url, e });
      if (e && e.status === 403) setStatus(statusEl, "Permission denied.", true);
      else if (e && e.status === 404) setStatus(statusEl, "Not found.", true);
      else setStatus(statusEl, "Error loading.", true);
      setGlobalError(extractApiErrorMessage(e));
      nextUrl = null;
      prevUrl = null;
    }
  }

  nextBtn.addEventListener("click", async () => {
    if (nextUrl) await load(nextUrl);
  });
  prevBtn.addEventListener("click", async () => {
    if (prevUrl) await load(prevUrl);
  });

  await load(initialUrl);

  return { reloadFirstPage: async () => load(initialUrl) };
}

export async function initGroupsList() {
  await loadMeAndInitShell();
  setGlobalError("");

  const statusEl = $("#groups-status");
  const resultsEl = $("#groups-results");
  const nextBtn = $("#groups-next");
  const prevBtn = $("#groups-prev");
  if (!statusEl || !resultsEl || !nextBtn || !prevBtn) return;

  await pagedListController({
    statusEl,
    resultsEl,
    nextBtn,
    prevBtn,
    initialUrl: "/api/v1/library/groups/",
    emptyText: "No groups.",
    render: renderGroupsList,
  });
}

export async function initGroupView() {
  const me = await loadMeAndInitShell();
  setGlobalError("");

  const root = $("#group-view-root");
  const summaryEl = $("#group-view-summary");
  const statusEl = $("#group-view-status");
  const titleEl = $("#group-view-title");
  const subtitleEl = $("#group-view-subtitle");
  const badgesEl = $("#group-view-badges");
  const descEl = $("#group-view-description");
  const editWrap = $("#group-view-edit-link-wrap");
  const editLink = $("#group-view-edit-link");

  const booksStatus = $("#group-view-books-status");
  const booksResults = $("#group-view-books-results");
  const booksNext = $("#group-view-books-next");
  const booksPrev = $("#group-view-books-prev");

  const membersNote = $("#group-view-members-note");
  const membersStatus = $("#group-view-members-status");
  const membersResults = $("#group-view-members-results");
  const membersNext = $("#group-view-members-next");
  const membersPrev = $("#group-view-members-prev");

  const shelvesStatus = $("#group-view-shelves-status");
  const shelvesResults = $("#group-view-shelves-results");
  const shelvesNext = $("#group-view-shelves-next");
  const shelvesPrev = $("#group-view-shelves-prev");

  if (
    !root ||
    !summaryEl ||
    !statusEl ||
    !titleEl ||
    !subtitleEl ||
    !badgesEl ||
    !descEl ||
    !booksStatus ||
    !booksResults ||
    !booksNext ||
    !booksPrev ||
    !membersStatus ||
    !membersResults ||
    !membersNext ||
    !membersPrev ||
    !membersNote
  ) {
    return;
  }

  initTabs(root);

  const groupId = root.getAttribute("data-group-id") || "";
  if (!groupId) return;

  setStatus(statusEl, "Loading…", false);
  visible(root, false);
  visible(summaryEl, false);
  visible(editWrap, false);

  let group = null;
  try {
    group = await fetchJSON(`/api/v1/library/groups/${encodeURIComponent(String(groupId))}/`);
  } catch (e) {
    console.error("Failed to load group", { groupId, e });
    if (e && e.status === 404) setStatus(statusEl, "Not found or not accessible.", true);
    else if (e && e.status === 403) setStatus(statusEl, "Permission denied.", true);
    else setStatus(statusEl, "Error loading group.", true);
    setGlobalError(extractApiErrorMessage(e));
    return;
  }

  const isPublicGroup = !!group.is_public_group;
  titleEl.textContent = group.name || "Group";

  subtitleEl.textContent = "";

  if (canEditGroupPage({ me, group })) {
    if (editLink) editLink.setAttribute("href", `/groups/${encodeURIComponent(String(groupId))}/edit/`);
    visible(editWrap, true);
  }

  // Stable details card above tabs.
  badgesEl.textContent = "";
  const badgesNode = document.createElement("div");
  if (isPublicGroup) {
    const b = document.createElement("span");
    b.className = "pill pill--owner";
    b.textContent = "Public";
    badgesNode.appendChild(b);
  }
  if (group.membership_role) {
    if (badgesNode.childNodes.length) badgesNode.appendChild(document.createTextNode(" "));
    const b2 = document.createElement("span");
    b2.className = "pill";
    b2.textContent = `Your role: ${group.membership_role}`;
    badgesNode.appendChild(b2);
  }
  badgesEl.appendChild(badgesNode);
  descEl.textContent = group.description || "";

  visible(summaryEl, true);
  visible(root, true);
  setStatus(statusEl, "", false);

  await pagedListController({
    statusEl: booksStatus,
    resultsEl: booksResults,
    nextBtn: booksNext,
    prevBtn: booksPrev,
    initialUrl: `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/books/`,
    emptyText: "No books in this group.",
    render: (payload) => renderBooksCompact(payload, { groupId, canRemove: false }),
  });

  membersNote.textContent = "";
  await pagedListController({
    statusEl: membersStatus,
    resultsEl: membersResults,
    nextBtn: membersNext,
    prevBtn: membersPrev,
    initialUrl: `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/`,
    emptyText: "No members.",
    render: (payload) => renderMembersReadOnly(payload),
  });

  if (shelvesStatus && shelvesResults && shelvesNext && shelvesPrev) {
    await pagedListController({
      statusEl: shelvesStatus,
      resultsEl: shelvesResults,
      nextBtn: shelvesNext,
      prevBtn: shelvesPrev,
      initialUrl: `/api/v1/shelves/?owner_group=${encodeURIComponent(String(groupId))}`,
      emptyText: "No shelves yet.",
      render: (payload) => renderGroupShelvesCompact(payload, { canEdit: false }),
    });
  }
}

export async function initGroupEdit() {
  const me = await loadMeAndInitShell();
  setGlobalError("");

  const root = $("#group-edit-root");
  const summaryEl = $("#group-edit-summary");
  const statusEl = $("#group-edit-status");
  const titleEl = $("#group-edit-title");
  const subtitleEl = $("#group-edit-subtitle");
  const notAllowedEl = $("#group-edit-not-allowed");

  const badgesEl = $("#group-edit-badges");
  const descPreviewEl = $("#group-edit-description-preview");
  const editForm = $("#group-edit-form");
  const descInput = $("#group-edit-description");
  const saveStatus = $("#group-edit-save-status");

  const bookSearchForm = $("#group-edit-book-search-form");
  const bookSearchInput = $("#group-edit-book-search");
  const bookSearchStatus = $("#group-edit-book-search-status");
  const bookSearchWrap = $("#group-edit-book-search-results-wrap");
  const bookSearchResults = $("#group-edit-book-search-results");
  const bookSearchPrev = $("#group-edit-book-search-prev");
  const bookSearchNext = $("#group-edit-book-search-next");

  const uuidDebugDetails = $("#group-edit-book-uuid-debug");
  const addBookForm = $("#group-edit-add-book");
  const addBookInput = $("#group-edit-book-id");
  const addBookStatus = $("#group-edit-add-book-status");
  const booksStatus = $("#group-edit-books-status");
  const booksResults = $("#group-edit-books-results");
  const booksNext = $("#group-edit-books-next");
  const booksPrev = $("#group-edit-books-prev");

  const membersNote = $("#group-edit-members-note");
  const addMemberForm = $("#group-edit-add-member");
  const addMemberUser = $("#group-edit-member-user");
  const addMemberRole = $("#group-edit-member-role");
  const addMemberStatus = $("#group-edit-add-member-status");
  const membersStatus = $("#group-edit-members-status");
  const membersResults = $("#group-edit-members-results");
  const membersNext = $("#group-edit-members-next");
  const membersPrev = $("#group-edit-members-prev");

  const shelvesNote = $("#group-edit-shelves-note");
  const shelvesActions = $("#group-edit-shelves-actions");
  const shelvesCreateLink = $("#group-edit-shelves-create-link");
  const shelvesStatus = $("#group-edit-shelves-status");
  const shelvesResults = $("#group-edit-shelves-results");
  const shelvesNext = $("#group-edit-shelves-next");
  const shelvesPrev = $("#group-edit-shelves-prev");

  if (
    !root ||
    !summaryEl ||
    !statusEl ||
    !titleEl ||
    !subtitleEl ||
    !notAllowedEl ||
    !badgesEl ||
    !descPreviewEl ||
    !editForm ||
    !descInput ||
    !saveStatus ||
    !bookSearchForm ||
    !bookSearchInput ||
    !bookSearchStatus ||
    !bookSearchWrap ||
    !bookSearchResults ||
    !bookSearchPrev ||
    !bookSearchNext ||
    !uuidDebugDetails ||
    !addBookForm ||
    !addBookInput ||
    !addBookStatus ||
    !booksStatus ||
    !booksResults ||
    !booksNext ||
    !booksPrev ||
    !membersNote ||
    !addMemberForm ||
    !addMemberUser ||
    !addMemberRole ||
    !addMemberStatus ||
    !membersStatus ||
    !membersResults ||
    !membersNext ||
    !membersPrev
  ) {
    return;
  }

  initTabs(root);

  const groupId = root.getAttribute("data-group-id") || "";
  if (!groupId) return;

  setStatus(statusEl, "Loading…", false);
  visible(root, false);
  visible(summaryEl, false);
  visible(notAllowedEl, false);

  let group = null;
  try {
    group = await fetchJSON(`/api/v1/library/groups/${encodeURIComponent(String(groupId))}/`);
  } catch (e) {
    console.error("Failed to load group", { groupId, e });
    if (e && e.status === 404) setStatus(statusEl, "Not found or not accessible.", true);
    else if (e && e.status === 403) setStatus(statusEl, "Permission denied.", true);
    else setStatus(statusEl, "Error loading group.", true);
    setGlobalError(extractApiErrorMessage(e));
    return;
  }

  const isPublicGroup = !!group.is_public_group;
  titleEl.textContent = group.name || "Group";
  subtitleEl.textContent = "";

  if (!canEditGroupPage({ me, group })) {
    setStatus(statusEl, "", false);
    visible(notAllowedEl, true);
    visible(root, false);
    visible(summaryEl, false);
    return;
  }

  // Stable details card above tabs.
  badgesEl.textContent = "";
  const badgesNode = document.createElement("div");
  if (isPublicGroup) {
    const b = document.createElement("span");
    b.className = "pill pill--owner";
    b.textContent = "Public";
    badgesNode.appendChild(b);
  }
  if (group.membership_role) {
    if (badgesNode.childNodes.length) badgesNode.appendChild(document.createTextNode(" "));
    const b2 = document.createElement("span");
    b2.className = "pill";
    b2.textContent = `Your role: ${group.membership_role}`;
    badgesNode.appendChild(b2);
  }
  badgesEl.appendChild(badgesNode);
  descPreviewEl.textContent = group.description || "";

  visible(summaryEl, true);
  visible(root, true);
  setStatus(statusEl, "", false);

  const allowDescriptionEdit = canEditGroupDescription({ me, group });
  descInput.value = group.description || "";
  visible(editForm, allowDescriptionEdit);

  function setSaveStatus(text, isError) {
    setStatus(saveStatus, text, isError);
  }
  function setAddBookStatus(text, isError) {
    setStatus(addBookStatus, text, isError);
  }
  function setBookSearchStatus(text, isError) {
    setStatus(bookSearchStatus, text, isError);
  }
  function setAddMemberStatus(text, isError) {
    setStatus(addMemberStatus, text, isError);
  }

  if (allowDescriptionEdit) {
    editForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      setSaveStatus("Saving…", false);
      setGlobalError("");

      try {
        const csrf = getCsrfToken();
        const headers = { Accept: "application/json", "Content-Type": "application/json" };
        if (csrf) headers["X-CSRFToken"] = csrf;

        await fetchJSONWithOptions(`/api/v1/library/groups/${encodeURIComponent(String(groupId))}/`, {
          method: "PATCH",
          headers,
          body: JSON.stringify({ description: descInput.value || "" }),
        });
        setSaveStatus("Saved.", false);
      } catch (e2) {
        console.error("Failed to save group description", { groupId, e2 });
        setSaveStatus(extractApiErrorMessage(e2), true);
        setGlobalError(extractApiErrorMessage(e2));
      }
    });
  }

  const allowBookManage = canManageGroupBooks({ me, group });
  visible(bookSearchForm, allowBookManage);
  visible(bookSearchWrap, false);
  // Keep the manual UUID add path as a collapsed debug-only fallback.
  visible(uuidDebugDetails, allowBookManage && (isManagerOrOwner(me) || isLibrarian(me)));
  visible(addBookForm, false);

  const booksCtl = await pagedListController({
    statusEl: booksStatus,
    resultsEl: booksResults,
    nextBtn: booksNext,
    prevBtn: booksPrev,
    initialUrl: `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/books/`,
    emptyText: "No books in this group.",
    render: (payload) => renderBooksCompact(payload, { groupId, canRemove: allowBookManage }),
  });

  if (allowBookManage) {
    const groupBookIds = new Set();

    async function loadGroupBookIds() {
      groupBookIds.clear();
      let url = `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/books/?page_size=200`;
      for (let i = 0; i < 20 && url; i++) {
        const payload = await fetchJSON(url);
        const results = Array.isArray(payload && payload.results) ? payload.results : [];
        for (const b of results) {
          if (b && b.id) groupBookIds.add(String(b.id));
        }
        url = payload.next || null;
      }
    }

    try {
      await loadGroupBookIds();
    } catch (e) {
      console.error("Failed to pre-load group book ids", { groupId, e });
    }

    function renderBookSearchResults(payload) {
      const results = Array.isArray(payload && payload.results) ? payload.results : [];
      if (!results.length) return "";

      return results
        .map((b) => {
          const id = b && b.id ? String(b.id) : "";
          const inGroup = id && groupBookIds.has(id);

          const title = b.title || "(Untitled)";
          const subtitle = b.subtitle ? ` <span class="muted">— ${escapeHtml(b.subtitle)}</span>` : "";
          const authors = Array.isArray(b.authors) ? b.authors.map((a) => a.name).filter(Boolean) : [];
          const series = b.series && b.series.name ? b.series.name : "";
          const seriesIndex = b.series_index != null && b.series_index !== "" ? String(b.series_index) : "";

          const fileBadge = b.file ? '<span class="pill">File</span>' : "";
          const inGroupBadge = inGroup ? '<span class="pill">Already in group</span>' : "";
          const badges = [fileBadge, inGroupBadge].filter(truthy).join(" ");

          const metaBits = [];
          if (authors.length) metaBits.push(escapeHtml(authors.join(", ")));
          if (series) metaBits.push(`${escapeHtml(series)}${seriesIndex ? ` #${escapeHtml(seriesIndex)}` : ""}`);
          const meta = metaBits.length ? `<div class="muted">${metaBits.join(" · ")}</div>` : "";

          const addBtn =
            !inGroup && id
              ? `<button class="button" type="button" data-action="add-book" data-book-id="${escapeHtml(
                  id
                )}">Add</button>`
              : "";

          return `
            <article class="book">
              <div style="display:flex; gap: 12px; justify-content: space-between; align-items: baseline; flex-wrap: wrap;">
                <div>
                  <h3 class="book__title" style="display:inline;">${escapeHtml(title)}${subtitle}</h3>
                  ${badges ? ` <span style="margin-left: 8px;">${badges}</span>` : ""}
                  ${meta}
                </div>
                ${addBtn ? `<div>${addBtn}</div>` : ""}
              </div>
            </article>
          `.trim();
        })
        .join("");
    }

    let searchNextUrl = null;
    let searchPrevUrl = null;
    let lastSearchUrl = null;

    async function loadBookSearch(url) {
      setBookSearchStatus("Searching…", false);
      bookSearchResults.innerHTML = "";
      bookSearchNext.disabled = true;
      bookSearchPrev.disabled = true;

      try {
        const payload = await fetchJSON(url);
        const results = Array.isArray(payload && payload.results) ? payload.results : [];
        if (!results.length) {
          setBookSearchStatus("No results.", false);
          searchNextUrl = null;
          searchPrevUrl = null;
          visible(bookSearchWrap, true);
          lastSearchUrl = url;
          return;
        }

        setBookSearchStatus(
          payload && payload.count != null ? `Showing ${results.length} of ${payload.count}.` : "",
          false
        );
        bookSearchResults.innerHTML = renderBookSearchResults(payload);
        searchNextUrl = payload.next || null;
        searchPrevUrl = payload.previous || null;
        bookSearchNext.disabled = !searchNextUrl;
        bookSearchPrev.disabled = !searchPrevUrl;
        visible(bookSearchWrap, true);
        lastSearchUrl = url;
      } catch (e) {
        console.error("Failed to search books", { groupId, url, e });
        if (e && e.status === 403) setBookSearchStatus("Permission denied.", true);
        else setBookSearchStatus("Search failed.", true);
        setGlobalError(extractApiErrorMessage(e));
        searchNextUrl = null;
        searchPrevUrl = null;
        visible(bookSearchWrap, true);
        lastSearchUrl = url;
      }
    }

    bookSearchForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const term = (bookSearchInput.value || "").trim();
      if (!term) {
        setBookSearchStatus("Enter a search term.", true);
        visible(bookSearchWrap, false);
        return;
      }
      const url = `/api/v1/library/books/?q=${encodeURIComponent(term)}`;
      await loadBookSearch(url);
    });

    bookSearchNext.addEventListener("click", async () => {
      if (searchNextUrl) await loadBookSearch(searchNextUrl);
    });
    bookSearchPrev.addEventListener("click", async () => {
      if (searchPrevUrl) await loadBookSearch(searchPrevUrl);
    });

    bookSearchResults.addEventListener("click", async (e) => {
      const target = e.target;
      if (!target || target.nodeType !== 1) return;
      if (target.getAttribute("data-action") !== "add-book") return;
      const bookId = target.getAttribute("data-book-id");
      if (!bookId) return;

      setBookSearchStatus("Adding…", false);
      setGlobalError("");

      try {
        const csrf = getCsrfToken();
        const headers = { Accept: "application/json", "Content-Type": "application/json" };
        if (csrf) headers["X-CSRFToken"] = csrf;

        await fetchJSONWithOptions(`/api/v1/library/groups/${encodeURIComponent(String(groupId))}/books/`, {
          method: "POST",
          headers,
          body: JSON.stringify({ book: bookId }),
        });

        groupBookIds.add(String(bookId));
        setBookSearchStatus("Added.", false);
        await booksCtl.reloadFirstPage();

        try {
          await loadGroupBookIds();
        } catch (e2) {
          console.error("Failed to refresh group book ids", e2);
        }

        if (lastSearchUrl) await loadBookSearch(lastSearchUrl);
      } catch (e2) {
        console.error("Failed to add book to group", { groupId, bookId, e2 });
        setBookSearchStatus(extractApiErrorMessage(e2), true);
        setGlobalError(extractApiErrorMessage(e2));
      }
    });
    addBookForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      setAddBookStatus("Adding…", false);
      setGlobalError("");

      const bookId = (addBookInput.value || "").trim();
      if (!bookId) {
        setAddBookStatus("Enter a book UUID.", true);
        return;
      }

      try {
        const csrf = getCsrfToken();
        const headers = { Accept: "application/json", "Content-Type": "application/json" };
        if (csrf) headers["X-CSRFToken"] = csrf;

        await fetchJSONWithOptions(`/api/v1/library/groups/${encodeURIComponent(String(groupId))}/books/`, {
          method: "POST",
          headers,
          body: JSON.stringify({ book: bookId }),
        });

        setAddBookStatus("Added.", false);
        addBookInput.value = "";
        await booksCtl.reloadFirstPage();
      } catch (e2) {
        console.error("Failed to add book to group", { groupId, bookId, e2 });
        setAddBookStatus(extractApiErrorMessage(e2), true);
        setGlobalError(extractApiErrorMessage(e2));
      }
    });

    booksResults.addEventListener("click", async (e) => {
      const target = e.target;
      if (!target || target.nodeType !== 1) return;
      if (target.getAttribute("data-action") !== "remove-book") return;
      const bookId = target.getAttribute("data-book-id");
      if (!bookId) return;

      setGlobalError("");
      setStatus(booksStatus, "Removing…", false);
      try {
        const csrf = getCsrfToken();
        const headers = { Accept: "application/json" };
        if (csrf) headers["X-CSRFToken"] = csrf;

        await fetchJSONWithOptions(
          `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/books/${encodeURIComponent(String(bookId))}/`,
          { method: "DELETE", headers }
        );
        await booksCtl.reloadFirstPage();
      } catch (e2) {
        console.error("Failed to remove book from group", { groupId, bookId, e2 });
        setStatus(booksStatus, extractApiErrorMessage(e2), true);
        setGlobalError(extractApiErrorMessage(e2));
      }
    });
  }

  const allowMembershipManage = canManageGroupMemberships(me);
  membersNote.textContent = allowMembershipManage
    ? ""
    : "Membership management is Manager/Owner only. This list is read-only for your account.";

  visible(addMemberForm, allowMembershipManage);
  if (isPublicGroup) {
    membersNote.textContent = allowMembershipManage
      ? "Public is the default/fallback group. Public cannot have curators; role remains reader. Public membership can be removed when another group remains (final removal restores Public)."
      : membersNote.textContent;
    addMemberRole.value = "reader";
    const curatorOpt = addMemberRole.querySelector('option[value="curator"]');
    if (curatorOpt) curatorOpt.disabled = true;
  }

  const membersCtl = await pagedListController({
    statusEl: membersStatus,
    resultsEl: membersResults,
    nextBtn: membersNext,
    prevBtn: membersPrev,
    initialUrl: `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/`,
    emptyText: "No members.",
    render: (payload) =>
      allowMembershipManage ? renderMembersManage(payload, { isPublicGroup }) : renderMembersReadOnly(payload),
  });

  if (allowMembershipManage) {
    try {
      const users = await loadAllManageableUsers();
      addMemberUser.textContent = "";
      for (const u of users) {
        const opt = document.createElement("option");
        opt.value = String(u.id);
        opt.textContent = `${u.username} (${u.email || ""})`;
        addMemberUser.appendChild(opt);
      }
    } catch (e) {
      console.error("Failed to load manageable users", e);
      addMemberUser.textContent = "";
      setAddMemberStatus("Error loading user list.", true);
    }

    addMemberForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      setAddMemberStatus("Adding…", false);
      setGlobalError("");

      const userId = addMemberUser.value;
      const role = isPublicGroup ? "reader" : addMemberRole.value;
      if (!userId) {
        setAddMemberStatus("Choose a user.", true);
        return;
      }

      try {
        const csrf = getCsrfToken();
        const headers = { Accept: "application/json", "Content-Type": "application/json" };
        if (csrf) headers["X-CSRFToken"] = csrf;

        await fetchJSONWithOptions(`/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/`, {
          method: "POST",
          headers,
          body: JSON.stringify({ user: Number(userId), role }),
        });

        setAddMemberStatus("Added.", false);
        await membersCtl.reloadFirstPage();
      } catch (e2) {
        console.error("Failed to add member", { groupId, e2 });
        setAddMemberStatus(extractApiErrorMessage(e2), true);
        setGlobalError(extractApiErrorMessage(e2));
      }
    });

    membersResults.addEventListener("click", async (e) => {
      const target = e.target;
      if (!target || target.nodeType !== 1) return;
      const action = target.getAttribute("data-action");
      const membershipId = target.getAttribute("data-membership-id");
      if (!action || !membershipId) return;

      if (action === "member-remove") {
        setStatus(membersStatus, "Removing…", false);
        try {
          const csrf = getCsrfToken();
          const headers = { Accept: "application/json" };
          if (csrf) headers["X-CSRFToken"] = csrf;

          await fetchJSONWithOptions(
            `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/${encodeURIComponent(
              String(membershipId)
            )}/`,
            { method: "DELETE", headers }
          );
          await membersCtl.reloadFirstPage();
        } catch (e2) {
          console.error("Failed to remove member", { groupId, membershipId, e2 });
          setStatus(membersStatus, extractApiErrorMessage(e2), true);
          setGlobalError(extractApiErrorMessage(e2));
        }
      }

      if (action === "member-save") {
        const select = membersResults.querySelector(
          `select[data-action="member-role"][data-membership-id="${membershipId}"]`
        );
        const role = select ? select.value : "reader";
        setStatus(membersStatus, "Saving…", false);
        try {
          const csrf = getCsrfToken();
          const headers = { Accept: "application/json", "Content-Type": "application/json" };
          if (csrf) headers["X-CSRFToken"] = csrf;

          await fetchJSONWithOptions(
            `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/${encodeURIComponent(
              String(membershipId)
            )}/`,
            { method: "PATCH", headers, body: JSON.stringify({ role }) }
          );
          await membersCtl.reloadFirstPage();
        } catch (e2) {
          console.error("Failed to update member role", { groupId, membershipId, e2 });
          setStatus(membersStatus, extractApiErrorMessage(e2), true);
          setGlobalError(extractApiErrorMessage(e2));
        }
      }
    });
  }

  if (shelvesNote) {
    shelvesNote.textContent =
      "Shelves organize presentation and do not grant book access. Group shelves contain only books assigned to this group.";
  }

  const allowShelfManage = canManageGroupBooks({ me, group });
  visible(shelvesActions, !!allowShelfManage);
  if (allowShelfManage && shelvesCreateLink) {
    shelvesCreateLink.setAttribute(
      "href",
      `/shelves/new/?owner_group=${encodeURIComponent(String(groupId))}`
    );
  }

  if (shelvesStatus && shelvesResults && shelvesNext && shelvesPrev) {
    await pagedListController({
      statusEl: shelvesStatus,
      resultsEl: shelvesResults,
      nextBtn: shelvesNext,
      prevBtn: shelvesPrev,
      initialUrl: `/api/v1/shelves/?owner_group=${encodeURIComponent(String(groupId))}`,
      emptyText: "No shelves yet.",
      render: (payload) => renderGroupShelvesCompact(payload, { canEdit: !!allowShelfManage }),
    });
  }
}

// Backwards-compatible export name (used by older page ids / imports).
export async function initGroupDetail() {
  return initGroupView();
}
