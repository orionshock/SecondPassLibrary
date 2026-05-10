import { fetchJSON, fetchJSONWithOptions, getCsrfToken, extractApiErrorMessage, summarizeFieldErrors } from './api.js';
import { $, escapeHtml, loadMeAndInitShell, setGlobalError, visible } from './layout.js';

function formatDateTime(value) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  try {
    return d.toLocaleString();
  } catch (_e) {
    return d.toISOString();
  }
}

export async function initUsersList() {
  const me = await loadMeAndInitShell();
  setGlobalError("");

  const notAllowedEl = $("#users-not-allowed");
  const createLink = $("#users-create-link");
  const filtersEl = $("#users-filters");
  const statusEl = $("#users-status");
  const resultsEl = $("#users-results");
  const nextBtn = $("#users-next");
  const prevBtn = $("#users-prev");

  if (!notAllowedEl || !createLink || !filtersEl || !statusEl || !resultsEl || !nextBtn || !prevBtn) {
    return;
  }

  const caps = me && me.capabilities ? me.capabilities : {};
  const allowed = !!caps.can_manage_users;

  visible(notAllowedEl, !allowed);
  visible(createLink, allowed);
  visible(filtersEl, allowed);

  let nextUrl = null;
  let prevUrl = null;
  let currentUrl = "/api/v1/accounts/users/";
  let currentResults = [];
  let totalUsersCount = null;
  let activeFilter = "all";

  function setStatus(text, isError) {
    statusEl.textContent = text;
    statusEl.classList.toggle("error", !!isError);
  }

  function updateStatusLabel() {
    if (!allowed) return;
    const total = totalUsersCount != null ? Number(totalUsersCount) : null;
    const pageCount = Array.isArray(currentResults) ? currentResults.length : 0;
    const filteredCount = (currentResults || []).filter((u) => passesFilter(u, activeFilter)).length;
    if (total != null && activeFilter && activeFilter !== "all") {
      setStatus(`Showing ${filteredCount} filtered users on this page. Total users: ${total}.`, false);
    } else if (total != null) {
      setStatus(`Showing ${pageCount} of ${total}.`, false);
    } else {
      setStatus("", false);
    }
  }

  function curatedGroupsFromUser(user) {
    const groups = Array.isArray(user && user.groups) ? user.groups : [];
    const curated = groups.filter((g) => (g && g.membership_role) === "curator");
    return curated.map((g) => g.name || g.slug || "").filter(Boolean);
  }

  function groupsSummary(user) {
    const groups = Array.isArray(user && user.groups) ? user.groups : [];
    if (!groups.length) return "";
    return groups
      .map((g) => {
        const name = g.name || g.slug || "";
        if (!name) return "";
        const badge = g.membership_role ? ` (${g.membership_role})` : "";
        return `${name}${badge}`;
      })
      .filter(Boolean)
      .join(", ");
  }

  function passesFilter(user, filter) {
    if (!user) return false;
    if (filter === "inactive") return user.is_active === false;
    if (filter === "readers") return (user.role || "") === "reader";
    if (filter === "librarians") return (user.role || "") === "librarian";
    if (filter === "curators") return curatedGroupsFromUser(user).length > 0;
    if (filter === "managers") return user.is_owner === true || (user.role || "") === "manager";
    return true;
  }

  function setActiveFilter(filter) {
    activeFilter = filter || "all";
    const buttons = filtersEl.querySelectorAll("button[data-filter]");
    for (const btn of buttons) {
      const isActive = btn.getAttribute("data-filter") === activeFilter;
      btn.setAttribute("aria-pressed", isActive ? "true" : "false");
    }
    render();
    updateStatusLabel();
  }

  function renderRow(user) {
    const id = user && user.id != null ? String(user.id) : "";
    const username = user.username || "";
    const email = user.email || "";
    const role = user.is_owner ? "manager" : user.role || "reader";
    const isOwner = !!user.is_owner;
    const isActive = user.is_active !== false;
    const lastLogin = user.last_login ? formatDateTime(user.last_login) : "";

    const ownerBadge = isOwner ? ' <span class="pill pill--owner">Owner</span>' : "";
    const roleBadge = `<span class="pill">${escapeHtml(role)}</span>`;
    const activeBadge = isActive ? '<span class="pill">active</span>' : '<span class="pill">inactive</span>';

    const curated = curatedGroupsFromUser(user);
    const curatesLine = curated.length ? `<div class="user-row__line">Curates: ${escapeHtml(curated.join(", "))}</div>` : "";

    const groupText = groupsSummary(user);
    const groupsLine = groupText ? `<div class="user-row__line">Groups: ${escapeHtml(groupText)}</div>` : `<div class="user-row__line muted">Groups: (none)</div>`;

    const lastLoginLine = lastLogin ? `<div class="user-row__line">Last login: ${escapeHtml(lastLogin)}</div>` : '<div class="user-row__line muted">Last login: (never)</div>';

    const editHref = id ? `/users/${encodeURIComponent(String(id))}/edit/` : "#";

    return `
      <article class="user-row">
        <div class="user-row__main">
          <div class="user-row__title">${escapeHtml(username)}${ownerBadge}</div>
          <div style="margin-top: 6px; display: flex; gap: 8px; flex-wrap: wrap;">
            ${roleBadge}
            ${activeBadge}
          </div>
        </div>
        <div class="user-row__meta">
          ${email ? `<div class="user-row__line">${escapeHtml(email)}</div>` : '<div class="user-row__line muted">(no email)</div>'}
          ${lastLoginLine}
          ${groupsLine}
          ${curatesLine}
        </div>
        <div class="user-row__actions">
          <a class="button" href="${escapeHtml(editHref)}">Edit</a>
        </div>
      </article>
    `.trim();
  }

  function render() {
    resultsEl.innerHTML = "";
    if (!allowed) return;

    const filtered = (currentResults || []).filter((u) => passesFilter(u, activeFilter));
    if (filtered.length === 0) {
      resultsEl.innerHTML = '<div class="muted">No users match this filter on this page.</div>';
      return;
    }
    resultsEl.innerHTML = filtered.map(renderRow).join("");
  }

  async function load(url) {
    setGlobalError("");
    setStatus("Loading users…", false);
    resultsEl.innerHTML = "";
    nextBtn.disabled = true;
    prevBtn.disabled = true;

    currentUrl = url;

    if (!allowed) {
      setStatus("Not allowed.", true);
      return;
    }

    try {
      const payload = await fetchJSON(url);
      const results = Array.isArray(payload && payload.results) ? payload.results : [];
      currentResults = results;
      totalUsersCount = payload && payload.count != null ? payload.count : null;

      if (results.length === 0) {
        setStatus("No users.", false);
        nextUrl = null;
        prevUrl = null;
        render();
        return;
      }

      nextUrl = payload.next || null;
      prevUrl = payload.previous || null;
      nextBtn.disabled = !nextUrl;
      prevBtn.disabled = !prevUrl;

      render();
      updateStatusLabel();
    } catch (e) {
      console.error("Failed to load users", { url, e });
      setStatus("Error loading users.", true);
      setGlobalError(extractApiErrorMessage(e));
      nextUrl = null;
      prevUrl = null;
    }
  }

  filtersEl.addEventListener("click", (e) => {
    const target = e.target;
    if (!target || target.nodeType !== 1) return;
    if (target.tagName !== "BUTTON") return;
    const filter = target.getAttribute("data-filter");
    if (!filter) return;
    setActiveFilter(filter);
  });

  setActiveFilter("all");
  await load(currentUrl);

  nextBtn.addEventListener("click", async () => {
    if (nextUrl) await load(nextUrl);
  });
  prevBtn.addEventListener("click", async () => {
    if (prevUrl) await load(prevUrl);
  });
}

export async function initUserEdit() {
  const me = await loadMeAndInitShell();
  setGlobalError("");

  const root = $("#user-edit");
  const notAllowedEl = $("#user-edit-not-allowed");
  const statusEl = $("#user-edit-status");
  const cardEl = $("#user-edit-card");
  const form = $("#user-edit-form");
  const usernameEl = $("#user-edit-username");
  const groupsEl = $("#user-edit-groups");
  const emailInput = $("#user-edit-email");
  const firstInput = $("#user-edit-first");
  const lastInput = $("#user-edit-last");
  const roleSelect = $("#user-edit-role");
  const activeSelect = $("#user-edit-active");
  const mustChangeInput = $("#user-edit-must-change");
  const submitBtn = $("#user-edit-submit");
  const saveStatus = $("#user-edit-save-status");

  const passwordCard = $("#user-password-card");
  const resetBtn = $("#user-reset-password-btn");
  const resetStatus = $("#user-reset-password-status");
  const resetResult = $("#user-reset-password-result");
  const resetCopy = $("#user-reset-password-copy");

  const membershipsCard = $("#user-memberships-card");
  const membershipsStatus = $("#user-memberships-status");
  const membershipsResults = $("#user-memberships-results");
  const addForm = $("#user-memberships-add-form");
  const addGroupSelect = $("#user-memberships-add-group");
  const addRoleSelect = $("#user-memberships-add-role");
  const addSubmitBtn = $("#user-memberships-add-submit");
  const addStatus = $("#user-memberships-add-status");

  if (
    !root ||
    !notAllowedEl ||
    !statusEl ||
    !cardEl ||
    !form ||
    !usernameEl ||
    !groupsEl ||
    !emailInput ||
    !firstInput ||
    !lastInput ||
    !roleSelect ||
    !activeSelect ||
    !mustChangeInput ||
    !submitBtn ||
    !saveStatus ||
    !passwordCard ||
    !resetBtn ||
    !resetStatus ||
    !resetResult ||
    !resetCopy ||
    !membershipsCard ||
    !membershipsStatus ||
    !membershipsResults ||
    !addForm ||
    !addGroupSelect ||
    !addRoleSelect ||
    !addSubmitBtn ||
    !addStatus
  ) {
    return;
  }

  const userId = root.dataset ? root.dataset.userId : "";
  if (!userId) {
    statusEl.textContent = "Missing user id.";
    statusEl.classList.add("error");
    return;
  }

  const caps = me && me.capabilities ? me.capabilities : {};
  const allowed = !!caps.can_manage_users;
  const canManageMemberships = !!caps.can_manage_group_memberships;

  visible(notAllowedEl, !allowed);
  visible(cardEl, allowed);
  visible(membershipsCard, allowed && canManageMemberships);

  function setStatus(text, isError) {
    statusEl.textContent = text || "";
    statusEl.classList.toggle("error", !!isError);
  }

  function setSaveStatus(text, isError) {
    saveStatus.textContent = text || "";
    saveStatus.classList.toggle("error", !!isError);
  }

  function setResetStatus(text, isError) {
    resetStatus.textContent = text || "";
    resetStatus.classList.toggle("error", !!isError);
  }

  function setMembershipsStatus(text, isError) {
    membershipsStatus.textContent = text || "";
    membershipsStatus.classList.toggle("error", !!isError);
  }

  function setAddStatus(text, isError) {
    addStatus.textContent = text || "";
    addStatus.classList.toggle("error", !!isError);
  }

  function setFormEnabled(on, message) {
    const disabled = !on;
    emailInput.disabled = disabled;
    firstInput.disabled = disabled;
    lastInput.disabled = disabled;
    roleSelect.disabled = disabled;
    activeSelect.disabled = disabled;
    mustChangeInput.disabled = disabled;
    submitBtn.disabled = disabled;
    if (message) setSaveStatus(message, true);
  }

  function setAddFormEnabled(on) {
    const disabled = !on;
    addGroupSelect.disabled = disabled;
    addRoleSelect.disabled = disabled;
    addSubmitBtn.disabled = disabled;
  }

  function applyRoleOptions() {
    const canSetManager = !!(me && me.is_owner);
    const mgrOpt = roleSelect.querySelector('option[value="manager"]');
    if (mgrOpt) mgrOpt.disabled = !canSetManager;
    if (!canSetManager && roleSelect.value === "manager") {
      roleSelect.value = "reader";
    }
  }

  function renderGroups(groups) {
    if (!Array.isArray(groups) || groups.length === 0) return '<div class="muted">No group memberships.</div>';
    return groups
      .map((g) => {
        const href = g.id ? `/groups/${encodeURIComponent(String(g.id))}/` : "#";
        const badge = g.is_public_group ? ' <span class="pill pill--owner">Public</span>' : "";
        return `<div><a href="${escapeHtml(href)}">${escapeHtml(g.name || g.slug || "")}</a>${badge} <span class="muted">(${escapeHtml(g.membership_role || "")})</span></div>`;
      })
      .join("");
  }

  function renderMembershipControls(groups) {
    const list = Array.isArray(groups) ? groups : [];
    if (!list.length) return '<div class="muted">No group memberships.</div>';

    return list
      .map((g) => {
        const groupId = g.id ? String(g.id) : "";
        const membershipId = g.membership_id ? String(g.membership_id) : "";
        const name = g.name || g.slug || "";
        const slug = g.slug || "";
        const role = g.membership_role || "reader";
        const isPublic = !!g.is_public_group;

        const publicBadge = isPublic ? ' <span class="pill pill--owner">Public</span>' : "";
        const disabled = isPublic ? "disabled" : "";
        const note = isPublic ? '<div class="muted">Public memberships cannot be removed; role remains reader.</div>' : "";

        return `
          <article class="book">
            <h3 class="book__title">${escapeHtml(name)}${publicBadge}</h3>
            <div class="book__meta">
              <div class="muted">${escapeHtml(slug)}</div>
              <div>Role: <select data-action="membership-role" data-group-id="${escapeHtml(groupId)}" data-membership-id="${escapeHtml(membershipId)}" ${disabled}>
                <option value="reader" ${role === "reader" ? "selected" : ""}>reader</option>
                <option value="curator" ${role === "curator" ? "selected" : ""} ${disabled}>curator</option>
              </select></div>
              ${note}
            </div>
            <div style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap;">
              <button class="button" type="button" data-action="membership-save" data-group-id="${escapeHtml(groupId)}" data-membership-id="${escapeHtml(membershipId)}" ${disabled}>Save role</button>
              <button class="button" type="button" data-action="membership-remove" data-group-id="${escapeHtml(groupId)}" data-membership-id="${escapeHtml(membershipId)}" ${disabled}>Remove</button>
            </div>
          </article>
        `.trim();
      })
      .join("");
  }

  async function loadAllGroups() {
    const groups = [];
    let url = "/api/v1/library/groups/";
    for (let i = 0; i < 10 && url; i++) {
      const payload = await fetchJSON(url);
      const results = Array.isArray(payload && payload.results) ? payload.results : [];
      for (const g of results) groups.push(g);
      url = payload.next || null;
    }
    return groups;
  }

  function refreshAddGroupOptions(allGroups, userGroups) {
    const existing = new Set((Array.isArray(userGroups) ? userGroups : []).map((g) => String(g.id)));
    addGroupSelect.innerHTML = "";

    const selectable = (Array.isArray(allGroups) ? allGroups : [])
      .filter((g) => g && g.id && !existing.has(String(g.id)))
      .filter((g) => !(g && g.slug === "public"));

    if (!selectable.length) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "(no groups available)";
      addGroupSelect.appendChild(opt);
      addGroupSelect.disabled = true;
      addSubmitBtn.disabled = true;
      return;
    }

    addGroupSelect.disabled = false;
    addSubmitBtn.disabled = false;

    for (const g of selectable) {
      const opt = document.createElement("option");
      opt.value = String(g.id);
      opt.textContent = g.name ? `${g.name} (${g.slug})` : String(g.slug || g.id);
      addGroupSelect.appendChild(opt);
    }
  }

  if (!allowed) {
    setStatus("Not allowed.", true);
    visible(cardEl, false);
    visible(membershipsCard, false);
    return;
  }

  setStatus("Loading…", false);
  let original = null;
  let allGroups = null;
  let canResetPassword = false;

  try {
    const payload = await fetchJSON(`/api/v1/accounts/users/${encodeURIComponent(String(userId))}/`);
    original = payload;
    usernameEl.textContent = payload.username || "";
    groupsEl.innerHTML = renderGroups(payload.groups);
    emailInput.value = payload.email || "";
    firstInput.value = payload.first_name || "";
    lastInput.value = payload.last_name || "";
    roleSelect.value = payload.role || "reader";
    activeSelect.value = payload.is_active === false ? "false" : "true";
    mustChangeInput.checked = !!payload.must_change_password;

    applyRoleOptions();

    setStatus("", false);
    setSaveStatus("", false);

    if (payload.is_owner) {
      setFormEnabled(false, "Owner cannot be edited here.");
    } else if (!me.is_owner && payload.role === "manager") {
      setFormEnabled(false, "Only Owner can edit Managers.");
    } else {
      setFormEnabled(true, "");
    }

    // Password reset visibility rules (also enforced server-side).
    canResetPassword = false;
    if (me && payload) {
      const isSelf = String(me.username || "") === String(payload.username || "");
      const actorIsManager = !me.is_owner && String(me.role || "") === "manager";
      const actorIsOwner = !!me.is_owner;

      if (!isSelf) {
        if (actorIsOwner) {
          canResetPassword = true;
        } else if (actorIsManager) {
          canResetPassword = !payload.is_owner && String(payload.role || "") !== "manager";
        }
      }
    }
    visible(passwordCard, canResetPassword);
    visible(resetResult, false);
    resetCopy.value = "";
    setResetStatus("", false);

    if (canManageMemberships) {
      setMembershipsStatus("", false);
      membershipsResults.innerHTML = renderMembershipControls(payload.groups);
      allGroups = await loadAllGroups();
      refreshAddGroupOptions(allGroups, payload.groups);
      setAddStatus("", false);
    }
  } catch (e) {
    console.error("Failed to load user", { userId, e });
    setStatus(extractApiErrorMessage(e), true);
    visible(cardEl, false);
    visible(membershipsCard, false);
    return;
  }

  async function refreshUserAndMemberships() {
    const payload = await fetchJSON(`/api/v1/accounts/users/${encodeURIComponent(String(userId))}/`);
    original = payload;
    usernameEl.textContent = payload.username || "";
    groupsEl.innerHTML = renderGroups(payload.groups);
    emailInput.value = payload.email || "";
    firstInput.value = payload.first_name || "";
    lastInput.value = payload.last_name || "";
    roleSelect.value = payload.role || "reader";
    activeSelect.value = payload.is_active === false ? "false" : "true";
    mustChangeInput.checked = !!payload.must_change_password;
    applyRoleOptions();

    if (canManageMemberships) {
      membershipsResults.innerHTML = renderMembershipControls(payload.groups);
      if (!allGroups) allGroups = await loadAllGroups();
      refreshAddGroupOptions(allGroups, payload.groups);
    }
    return payload;
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    setGlobalError("");
    setSaveStatus("Saving…", false);

    if (!original) {
      setSaveStatus("User not loaded.", true);
      return;
    }

    if (original.is_owner) {
      setSaveStatus("Owner cannot be edited here.", true);
      return;
    }
    if (!me.is_owner && original.role === "manager") {
      setSaveStatus("Only Owner can edit Managers.", true);
      return;
    }

    const desired = {
      email: emailInput.value || "",
      first_name: firstInput.value || "",
      last_name: lastInput.value || "",
      role: roleSelect.value || "reader",
      is_active: activeSelect.value === "true",
      must_change_password: !!mustChangeInput.checked,
    };

    const patch = {};
    for (const key of Object.keys(desired)) {
      if (String(desired[key]) !== String(original[key])) {
        patch[key] = desired[key];
      }
    }

    if (Object.keys(patch).length === 0) {
      setSaveStatus("No changes.", false);
      return;
    }

    if (!me.is_owner && patch.role === "manager") {
      setSaveStatus("Only Owner can assign manager.", true);
      return;
    }

    try {
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json", "Content-Type": "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;

      const updated = await fetchJSONWithOptions(`/api/v1/accounts/users/${encodeURIComponent(String(userId))}/`, {
        method: "PATCH",
        headers,
        body: JSON.stringify(patch),
      });

      original = updated;
      usernameEl.textContent = updated.username || "";
      groupsEl.innerHTML = renderGroups(updated.groups);
      emailInput.value = updated.email || "";
      firstInput.value = updated.first_name || "";
      lastInput.value = updated.last_name || "";
      roleSelect.value = updated.role || "reader";
      activeSelect.value = updated.is_active === false ? "false" : "true";
      applyRoleOptions();

      setSaveStatus("Saved.", false);
    } catch (e2) {
      console.error("Failed to save user", { userId, e2 });
      const msg = extractApiErrorMessage(e2);
      const fieldMsg = summarizeFieldErrors(e2 && e2.body ? e2.body : null);
      setSaveStatus(fieldMsg ? `${msg} (${fieldMsg})` : msg, true);
      setGlobalError(msg);
    }
  });

  resetBtn.addEventListener("click", async () => {
    setGlobalError("");
    setResetStatus("Resetting…", false);
    visible(resetResult, false);
    resetCopy.value = "";

    if (!canResetPassword) {
      setResetStatus("Not allowed.", true);
      return;
    }

    try {
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json", "Content-Type": "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;

      const payload = await fetchJSONWithOptions(
        `/api/v1/accounts/users/${encodeURIComponent(String(userId))}/reset-password/`,
        { method: "POST", headers }
      );

      const copyBlock = payload && payload.copy_block ? String(payload.copy_block) : "";
      if (!copyBlock) throw new Error("Unexpected response from server.");

      resetCopy.value = copyBlock;
      visible(resetResult, true);
      setResetStatus("Reset.", false);

      // Refresh user to show must_change_password=true.
      await refreshUserAndMemberships();
    } catch (e2) {
      console.error("Failed to reset password", { userId, e2 });
      const msg = extractApiErrorMessage(e2);
      setResetStatus(msg, true);
      setGlobalError(msg);
    }
  });

  if (canManageMemberships) {
    membershipsResults.addEventListener("click", async (e) => {
      const target = e.target;
      if (!target || target.nodeType !== 1) return;
      const action = target.getAttribute("data-action");
      if (action !== "membership-save" && action !== "membership-remove") return;

      const groupId = target.getAttribute("data-group-id") || "";
      const membershipId = target.getAttribute("data-membership-id") || "";
      if (!groupId || !membershipId) {
        setMembershipsStatus("Missing membership identifiers.", true);
        return;
      }

      try {
        setMembershipsStatus(action === "membership-save" ? "Saving role…" : "Removing…", false);
        setGlobalError("");

        const csrf = getCsrfToken();
        const headers = { Accept: "application/json", "Content-Type": "application/json" };
        if (csrf) headers["X-CSRFToken"] = csrf;

        if (action === "membership-save") {
          const container = target.closest("article");
          const roleSelectEl = container ? container.querySelector('select[data-action="membership-role"]') : null;
          const newRole = roleSelectEl ? roleSelectEl.value : "reader";
          await fetchJSONWithOptions(
            `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/${encodeURIComponent(String(membershipId))}/`,
            {
              method: "PATCH",
              headers,
              body: JSON.stringify({ role: newRole }),
            }
          );
        } else {
          await fetchJSONWithOptions(
            `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/${encodeURIComponent(String(membershipId))}/`,
            { method: "DELETE", headers }
          );
        }

        await refreshUserAndMemberships();
        setMembershipsStatus(action === "membership-save" ? "Saved." : "Removed.", false);
      } catch (e2) {
        console.error("Membership action failed", { action, groupId, membershipId, e2 });
        const msg = extractApiErrorMessage(e2);
        setMembershipsStatus(msg, true);
        setGlobalError(msg);
      }
    });

    addForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      setGlobalError("");
      setAddStatus("Adding…", false);
      setAddFormEnabled(false);

      const groupId = addGroupSelect.value || "";
      const role = addRoleSelect.value || "reader";
      if (!groupId) {
        setAddStatus("Select a group.", true);
        setAddFormEnabled(true);
        return;
      }

      try {
        const csrf = getCsrfToken();
        const headers = { Accept: "application/json", "Content-Type": "application/json" };
        if (csrf) headers["X-CSRFToken"] = csrf;

        await fetchJSONWithOptions(`/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/`, {
          method: "POST",
          headers,
          body: JSON.stringify({ user: String(userId), role }),
        });

        await refreshUserAndMemberships();
        setAddStatus("Added.", false);
      } catch (e2) {
        console.error("Failed to add membership", { userId, e2 });
        const msg = extractApiErrorMessage(e2);
        const fieldMsg = summarizeFieldErrors(e2 && e2.body ? e2.body : null);
        setAddStatus(fieldMsg ? `${msg} (${fieldMsg})` : msg, true);
        setGlobalError(msg);
      } finally {
        setAddFormEnabled(true);
      }
    });
  } else {
    visible(membershipsCard, false);
  }
}

export async function initUserNew() {
  const me = await loadMeAndInitShell();
  setGlobalError("");

  const notAllowedEl = $("#user-new-not-allowed");
  const statusEl = $("#user-new-status");
  const formCard = $("#user-new-form-card");
  const form = $("#user-new-form");
  const usernameInput = $("#user-new-username");
  const emailInput = $("#user-new-email");
  const firstInput = $("#user-new-first");
  const lastInput = $("#user-new-last");
  const roleSelect = $("#user-new-role");
  const activeInput = $("#user-new-active");
  const submitBtn = $("#user-new-submit");
  const submitStatus = $("#user-new-submit-status");

  const successCard = $("#user-new-success");
  const createdUsername = $("#user-new-created-username");
  const createdPassword = $("#user-new-created-password");

  if (
    !notAllowedEl ||
    !statusEl ||
    !formCard ||
    !form ||
    !usernameInput ||
    !emailInput ||
    !firstInput ||
    !lastInput ||
    !roleSelect ||
    !activeInput ||
    !submitBtn ||
    !submitStatus ||
    !successCard ||
    !createdUsername ||
    !createdPassword
  ) {
    return;
  }

  const caps = me && me.capabilities ? me.capabilities : {};
  const allowed = !!caps.can_manage_users;

  visible(notAllowedEl, !allowed);
  visible(formCard, allowed);

  if (!allowed) {
    statusEl.textContent = "Not allowed.";
    statusEl.classList.add("error");
    return;
  }

  statusEl.textContent = "";
  statusEl.classList.remove("error");

  const canCreateManager = !!(me && me.is_owner);
  const mgrOpt = roleSelect.querySelector('option[value="manager"]');
  if (mgrOpt) mgrOpt.disabled = !canCreateManager;
  if (!canCreateManager && roleSelect.value === "manager") {
    roleSelect.value = "reader";
  }

  function setSubmitStatus(text, isError) {
    submitStatus.textContent = text || "";
    submitStatus.classList.toggle("error", !!isError);
  }

  function setFormEnabled(on) {
    const disabled = !on;
    usernameInput.disabled = disabled;
    emailInput.disabled = disabled;
    firstInput.disabled = disabled;
    lastInput.disabled = disabled;
    roleSelect.disabled = disabled;
    activeInput.disabled = disabled;
    submitBtn.disabled = disabled;
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    setGlobalError("");
    setSubmitStatus("Creating…", false);
    setFormEnabled(false);

    const payload = {
      username: (usernameInput.value || "").trim(),
      email: (emailInput.value || "").trim(),
      first_name: (firstInput.value || "").trim(),
      last_name: (lastInput.value || "").trim(),
      role: roleSelect.value || "reader",
      is_active: !!activeInput.checked,
    };

    if (!payload.username) {
      setSubmitStatus("Username is required.", true);
      setFormEnabled(true);
      return;
    }

    if (!canCreateManager && payload.role === "manager") {
      setSubmitStatus("Only Owner can create Managers.", true);
      setFormEnabled(true);
      return;
    }

    try {
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json", "Content-Type": "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;

      const created = await fetchJSONWithOptions("/api/v1/accounts/users/", {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });

      const u = created && created.user ? created.user : null;
      const pw = created && created.temporary_password ? String(created.temporary_password) : "";

      if (!u || !pw) {
        throw new Error("Unexpected response from server.");
      }

      createdUsername.textContent = u.username || payload.username;
      createdPassword.textContent = pw;

      visible(formCard, false);
      visible(successCard, true);
      setSubmitStatus("", false);
    } catch (e2) {
      console.error("Failed to create user", { e2 });
      const msg = extractApiErrorMessage(e2);
      const fieldMsg = summarizeFieldErrors(e2 && e2.body ? e2.body : null);
      setSubmitStatus(fieldMsg ? `${msg} (${fieldMsg})` : msg, true);
      setGlobalError(msg);
      setFormEnabled(true);
    }
  });
}

