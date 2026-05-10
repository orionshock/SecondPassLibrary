import { fetchJSON, fetchJSONWithOptions, getCsrfToken, extractApiErrorMessage, summarizeFieldErrors } from './api.js';
import { $, escapeHtml, loadMeAndInitShell, setGlobalError, visible } from './layout.js';

function renderGroupsList(payload) {
  const results = Array.isArray(payload && payload.results) ? payload.results : [];
  if (results.length === 0) return "";

  return results
    .map((g) => {
      const name = g.name || "";
      const slug = g.slug || "";
      const membershipRole = g.membership_role || "";
      const isPublic = !!g.is_public_group;
      const href = g.id ? `/groups/${encodeURIComponent(String(g.id))}/` : "#";

      const badges = [
        isPublic ? '<span class="pill pill--owner">Public</span>' : "",
        membershipRole ? `<span class="pill">${escapeHtml(membershipRole)}</span>` : "",
      ]
        .filter(Boolean)
        .join(" ");

      return `
        <article class="book">
          <h3 class="book__title"><a href="${escapeHtml(href)}">${escapeHtml(name)}</a></h3>
          <div class="book__meta">
            <div>Slug: <code>${escapeHtml(slug)}</code></div>
            ${badges ? `<div>${badges}</div>` : ""}
          </div>
        </article>
      `.trim();
    })
    .join("");
}

export async function initGroupsList() {
  await loadMeAndInitShell();
  setGlobalError("");

  const statusEl = $("#groups-status");
  const resultsEl = $("#groups-results");
  const nextBtn = $("#groups-next");
  const prevBtn = $("#groups-prev");
  if (!statusEl || !resultsEl || !nextBtn || !prevBtn) return;

  let nextUrl = null;
  let prevUrl = null;

  function setStatus(text, isError) {
    statusEl.textContent = text;
    statusEl.classList.toggle("error", !!isError);
  }

  async function load(url) {
    setStatus("Loading…", false);
    resultsEl.innerHTML = "";
    nextBtn.disabled = true;
    prevBtn.disabled = true;

    try {
      const payload = await fetchJSON(url);
      const results = Array.isArray(payload && payload.results) ? payload.results : [];
      if (results.length === 0) {
        setStatus("No groups.", false);
        nextUrl = null;
        prevUrl = null;
        return;
      }

      setStatus(payload && payload.count != null ? `Showing ${results.length} of ${payload.count}.` : "", false);
      resultsEl.innerHTML = renderGroupsList(payload);

      nextUrl = payload.next || null;
      prevUrl = payload.previous || null;
      nextBtn.disabled = !nextUrl;
      prevBtn.disabled = !prevUrl;
    } catch (e) {
      console.error("Failed to load groups", { url, e });
      if (e && e.status === 403) {
        setStatus("Permission denied.", true);
      } else if (e && e.status === 404) {
        setStatus("Not found.", true);
      } else {
        setStatus("Error loading groups.", true);
      }
      setGlobalError(extractApiErrorMessage(e));
      nextUrl = null;
      prevUrl = null;
    }
  }

  await load("/api/v1/library/groups/");

  nextBtn.addEventListener("click", async () => {
    if (nextUrl) await load(nextUrl);
  });
  prevBtn.addEventListener("click", async () => {
    if (prevUrl) await load(prevUrl);
  });
}

function renderGroupBooks(payload, groupId) {
  const results = Array.isArray(payload && payload.results) ? payload.results : [];
  if (results.length === 0) return "";

  return results
    .map((b) => {
      const title = b.title || "(Untitled)";
      const subtitle = b.subtitle ? ` <span class="muted">— ${escapeHtml(b.subtitle)}</span>` : "";
      const bookHref = b.id ? `/library/books/${encodeURIComponent(String(b.id))}/` : null;
      const authors = Array.isArray(b.authors) ? b.authors.map((a) => a.name).filter(Boolean) : [];

      const removeBtn =
        b.id && groupId
          ? `<button class="button" type="button" data-action="remove-book" data-book-id="${escapeHtml(b.id)}">Remove from group</button>`
          : "";

      return `
        <article class="book">
          <h3 class="book__title">${
            bookHref
              ? `<a href="${escapeHtml(bookHref)}">${escapeHtml(title)}</a>${subtitle}`
              : `${escapeHtml(title)}${subtitle}`
          }</h3>
          <div class="book__meta">
            ${authors.length ? `<div>${escapeHtml(authors.join(", "))}</div>` : ""}
          </div>
          ${removeBtn ? `<div style="margin-top: 10px;">${removeBtn}</div>` : ""}
        </article>
      `.trim();
    })
    .join("");
}

export async function initGroupDetail() {
  const me = await loadMeAndInitShell();
  setGlobalError("");

  const summaryEl = $("#group-summary");
  const statusEl = $("#group-status");
  const titleEl = $("#group-title");
  const metaEl = $("#group-meta");

  const editSection = $("#group-edit");
  const editForm = $("#group-edit-form");
  const editStatus = $("#group-edit-status");
  const descInput = $("#group-description");
  const discSelect = null;
  const discNote = null;

  const booksSection = $("#group-books");
  const booksStatus = $("#group-books-status");
  const booksResults = $("#group-books-results");
  const booksNext = $("#group-books-next");
  const booksPrev = $("#group-books-prev");

  const addBookForm = $("#group-add-book");
  const addBookInput = $("#group-book-id");
  const addBookStatus = $("#group-add-book-status");

  const membersSection = $("#group-members");
  const membersNote = $("#group-members-note");
  const membersStatus = $("#group-members-status");
  const membersResults = $("#group-members-results");
  const membersNext = $("#group-members-next");
  const membersPrev = $("#group-members-prev");

  const addMemberForm = $("#group-add-member");
  const addMemberUser = $("#group-member-user");
  const addMemberRole = $("#group-member-role");
  const addMemberStatus = $("#group-add-member-status");

  if (
    !summaryEl ||
    !statusEl ||
    !titleEl ||
    !metaEl ||
    !editSection ||
    !editForm ||
    !editStatus ||
    !descInput ||
    !booksSection ||
    !booksStatus ||
    !booksResults ||
    !booksNext ||
    !booksPrev ||
    !addBookForm ||
    !addBookInput ||
    !addBookStatus ||
    !membersSection ||
    !membersNote ||
    !membersStatus ||
    !membersResults ||
    !membersNext ||
    !membersPrev ||
    !addMemberForm ||
    !addMemberUser ||
    !addMemberRole ||
    !addMemberStatus
  ) {
    return;
  }

  const groupId = summaryEl.dataset ? summaryEl.dataset.groupId : "";
  if (!groupId) {
    statusEl.textContent = "Missing group id.";
    statusEl.classList.add("error");
    return;
  }

  let isPublicGroup = false;
  let booksNextUrl = null;
  let booksPrevUrl = null;
  let membersNextUrl = null;
  let membersPrevUrl = null;
  const canManageMemberships = !!(me && me.capabilities && me.capabilities.can_manage_group_memberships);

  function setStatus(text, isError) {
    statusEl.textContent = text;
    statusEl.classList.toggle("error", !!isError);
  }

  function setBooksStatus(text, isError) {
    booksStatus.textContent = text;
    booksStatus.classList.toggle("error", !!isError);
  }

  function setEditStatus(text, isError) {
    editStatus.textContent = text || "";
    editStatus.classList.toggle("error", !!isError);
  }

  function setAddBookStatus(text, isError) {
    addBookStatus.textContent = text || "";
    addBookStatus.classList.toggle("error", !!isError);
  }

  function setMembersStatus(text, isError) {
    membersStatus.textContent = text;
    membersStatus.classList.toggle("error", !!isError);
  }

  function setAddMemberStatus(text, isError) {
    addMemberStatus.textContent = text || "";
    addMemberStatus.classList.toggle("error", !!isError);
  }

  function renderMemberships(payload) {
    const results = Array.isArray(payload && payload.results) ? payload.results : [];
    if (results.length === 0) return "";

    return results
      .map((m) => {
        const isOwner = !!m.is_owner;
        const role = m.role || "reader";
        const removeDisabled = isPublicGroup ? "disabled" : "";
        const curatorDisabled = isPublicGroup ? "disabled" : "";

        const ownerBadge = isOwner ? ' <span class="pill pill--owner">Owner</span>' : "";
        const note = isPublicGroup ? '<div class="muted">Public memberships cannot be removed; role remains reader.</div>' : "";

        return `
          <article class="book">
            <h3 class="book__title">${escapeHtml(m.username || "")}${ownerBadge}</h3>
            <div class="book__meta">
              ${m.email ? `<div>${escapeHtml(m.email)}</div>` : ""}
              <div>Role: <select data-action="member-role" data-membership-id="${escapeHtml(m.id)}">
                <option value="reader" ${role === "reader" ? "selected" : ""}>reader</option>
                <option value="curator" ${role === "curator" ? "selected" : ""} ${curatorDisabled}>curator</option>
              </select></div>
              ${note}
            </div>
            <div style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap;">
              <button class="button" type="button" data-action="member-save" data-membership-id="${escapeHtml(m.id)}">Save role</button>
              <button class="button" type="button" data-action="member-remove" data-membership-id="${escapeHtml(m.id)}" ${removeDisabled}>Remove</button>
            </div>
          </article>
        `.trim();
      })
      .join("");
  }

  async function loadAllManageableUsers() {
    // Uses Manager/Owner users endpoint; fetch a few pages to populate a dropdown.
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

  async function loadMembers(url) {
    setMembersStatus("Loading…", false);
    membersResults.innerHTML = "";
    membersNext.disabled = true;
    membersPrev.disabled = true;

    try {
      const payload = await fetchJSON(url);
      const results = Array.isArray(payload && payload.results) ? payload.results : [];
      if (results.length === 0) {
        setMembersStatus("No members.", false);
        membersNextUrl = null;
        membersPrevUrl = null;
        return;
      }

      setMembersStatus(
        payload && payload.count != null ? `Showing ${results.length} of ${payload.count}.` : "",
        false
      );
      membersResults.innerHTML = renderMemberships(payload);
      membersNextUrl = payload.next || null;
      membersPrevUrl = payload.previous || null;
      membersNext.disabled = !membersNextUrl;
      membersPrev.disabled = !membersPrevUrl;
    } catch (e) {
      console.error("Failed to load memberships", { groupId, url, e });
      if (e && e.status === 403) setMembersStatus("Permission denied.", true);
      else if (e && e.status === 404) setMembersStatus("Not found.", true);
      else setMembersStatus("Error loading members.", true);
      setGlobalError(extractApiErrorMessage(e));
      membersNextUrl = null;
      membersPrevUrl = null;
    }
  }

  async function refreshMembersFirstPage() {
    await loadMembers(`/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/`);
  }

  async function loadGroup() {
    setStatus("Loading…", false);
    visible(summaryEl, false);
    visible(editSection, false);
    visible(booksSection, false);
    visible(membersSection, false);

    try {
      const group = await fetchJSON(`/api/v1/library/groups/${encodeURIComponent(String(groupId))}/`);
      const name = group.name || "Group";
      titleEl.textContent = name;

      isPublicGroup = !!group.is_public_group;
      const membershipRole = group.membership_role || "";

      const badges = [
        isPublicGroup ? '<span class="pill pill--owner">Public</span>' : "",
        membershipRole ? `<span class="pill">${escapeHtml(membershipRole)}</span>` : "",
      ]
        .filter(Boolean)
        .join(" ");

      metaEl.innerHTML = `
        <div class="kv">
          <div class="kv__k">Name</div><div class="kv__v">${escapeHtml(name)}</div>
          <div class="kv__k">Slug</div><div class="kv__v"><code>${escapeHtml(group.slug || "")}</code></div>
          <div class="kv__k">Badges</div><div class="kv__v">${badges || ""}</div>
          <div class="kv__k">Description</div><div class="kv__v">${escapeHtml(group.description || "")}</div>
        </div>
      `.trim();

      descInput.value = group.description || "";
      // discoverability removed

      visible(summaryEl, true);
      visible(editSection, true);
      visible(booksSection, true);

      // Membership management is Manager/Owner only.
      if (canManageMemberships) {
        visible(membersSection, true);
        if (isPublicGroup) {
          membersNote.textContent = "Public membership is required for all users. It cannot be removed, and cannot have curators.";
          addMemberRole.value = "reader";
          addMemberRole.querySelector('option[value="curator"]').disabled = true;
        } else {
          membersNote.textContent = "";
          addMemberRole.querySelector('option[value="curator"]').disabled = false;
        }
      } else {
        visible(membersSection, false);
      }

      setStatus("", false);
    } catch (e) {
      console.error("Failed to load group", { groupId, e });
      if (e && e.status === 404) setStatus("Not found or not accessible.", true);
      else if (e && e.status === 403) setStatus("Permission denied.", true);
      else setStatus("Error loading group.", true);
      setGlobalError(extractApiErrorMessage(e));
    }
  }

  async function loadBooks(url) {
    setBooksStatus("Loading…", false);
    booksResults.innerHTML = "";
    booksNext.disabled = true;
    booksPrev.disabled = true;

    try {
      const payload = await fetchJSON(url);
      const results = Array.isArray(payload && payload.results) ? payload.results : [];
      if (results.length === 0) {
        setBooksStatus("No books in this group.", false);
        booksNextUrl = null;
        booksPrevUrl = null;
        return;
      }

      setBooksStatus(payload && payload.count != null ? `Showing ${results.length} of ${payload.count}.` : "", false);
      booksResults.innerHTML = renderGroupBooks(payload, groupId);
      booksNextUrl = payload.next || null;
      booksPrevUrl = payload.previous || null;
      booksNext.disabled = !booksNextUrl;
      booksPrev.disabled = !booksPrevUrl;
    } catch (e) {
      console.error("Failed to load group books", { groupId, url, e });
      if (e && e.status === 404) setBooksStatus("Not found.", true);
      else if (e && e.status === 403) setBooksStatus("Permission denied.", true);
      else setBooksStatus("Error loading group books.", true);
      setGlobalError(extractApiErrorMessage(e));
      booksNextUrl = null;
      booksPrevUrl = null;
    }
  }

  async function refreshBooksFirstPage() {
    await loadBooks(`/api/v1/library/groups/${encodeURIComponent(String(groupId))}/books/`);
  }

  booksNext.addEventListener("click", async () => {
    if (booksNextUrl) await loadBooks(booksNextUrl);
  });
  booksPrev.addEventListener("click", async () => {
    if (booksPrevUrl) await loadBooks(booksPrevUrl);
  });

  membersNext.addEventListener("click", async () => {
    if (membersNextUrl) await loadMembers(membersNextUrl);
  });
  membersPrev.addEventListener("click", async () => {
    if (membersPrevUrl) await loadMembers(membersPrevUrl);
  });

  editForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    setEditStatus("Saving…", false);
    setGlobalError("");

    const payload = {
      description: descInput.value || "",
    };
    // discoverability removed

    try {
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json", "Content-Type": "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;

      await fetchJSONWithOptions(`/api/v1/library/groups/${encodeURIComponent(String(groupId))}/`, {
        method: "PATCH",
        headers,
        body: JSON.stringify(payload),
      });

      setEditStatus("Saved.", false);
      await loadGroup();
    } catch (e2) {
      console.error("Failed to save group presentation", { groupId, e2 });
      if (e2 && e2.status === 403) setEditStatus("Permission denied.", true);
      else setEditStatus("Save failed.", true);
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
      await refreshBooksFirstPage();
    } catch (e2) {
      console.error("Failed to add book to group", { groupId, bookId, e2 });
      if (e2 && e2.status === 403) setAddBookStatus("Permission denied.", true);
      else setAddBookStatus("Add failed.", true);
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
    setBooksStatus("Removing…", false);

    try {
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;

      await fetchJSONWithOptions(
        `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/books/${encodeURIComponent(String(bookId))}/`,
        { method: "DELETE", headers }
      );

      await refreshBooksFirstPage();
    } catch (e2) {
      console.error("Failed to remove book from group", { groupId, bookId, e2 });
      if (e2 && e2.status === 403) setBooksStatus("Permission denied.", true);
      else setBooksStatus("Remove failed.", true);
      setGlobalError(extractApiErrorMessage(e2));
    }
  });

  await loadGroup();
  await refreshBooksFirstPage();

  if (canManageMemberships) {
    // Populate add-member dropdown and load current memberships.
    try {
      const users = await loadAllManageableUsers();
      addMemberUser.innerHTML = users
        .map((u) => `<option value="${escapeHtml(u.id)}">${escapeHtml(u.username)} (${escapeHtml(u.email || "")})</option>`)
        .join("");
      visible(addMemberForm, true);
    } catch (e) {
      console.error("Failed to load manageable users for membership add", e);
      visible(addMemberForm, true);
      addMemberUser.innerHTML = "";
      setAddMemberStatus("Error loading user list.", true);
    }

    await refreshMembersFirstPage();

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

        await fetchJSONWithOptions(
          `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/`,
          { method: "POST", headers, body: JSON.stringify({ user: Number(userId), role }) }
        );

        setAddMemberStatus("Added.", false);
        await refreshMembersFirstPage();
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
        setMembersStatus("Removing…", false);
        try {
          const csrf = getCsrfToken();
          const headers = { Accept: "application/json" };
          if (csrf) headers["X-CSRFToken"] = csrf;

          await fetchJSONWithOptions(
            `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/${encodeURIComponent(String(membershipId))}/`,
            { method: "DELETE", headers }
          );
          await refreshMembersFirstPage();
        } catch (e2) {
          console.error("Failed to remove member", { groupId, membershipId, e2 });
          setMembersStatus("Remove failed.", true);
          setGlobalError(extractApiErrorMessage(e2));
        }
      }

      if (action === "member-save") {
        const select = membersResults.querySelector(
          `select[data-action="member-role"][data-membership-id="${membershipId}"]`
        );
        const role = select ? select.value : "reader";
        setMembersStatus("Saving…", false);
        try {
          const csrf = getCsrfToken();
          const headers = { Accept: "application/json", "Content-Type": "application/json" };
          if (csrf) headers["X-CSRFToken"] = csrf;

          await fetchJSONWithOptions(
            `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/${encodeURIComponent(String(membershipId))}/`,
            { method: "PATCH", headers, body: JSON.stringify({ role }) }
          );
          await refreshMembersFirstPage();
        } catch (e2) {
          console.error("Failed to update member role", { groupId, membershipId, e2 });
          setMembersStatus("Save failed.", true);
          setGlobalError(extractApiErrorMessage(e2));
        }
      }
    });
  }
}
