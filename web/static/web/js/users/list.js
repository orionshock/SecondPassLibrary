import { extractApiErrorMessage, fetchJSON } from "../api.js";
import { canManageUsers } from "../auth.js";
import {
  $,
  advancedLibraryGroupsEnabled,
  escapeHtml,
  loadMeAndInitShell,
  setGlobalError,
  visible,
} from "../layout.js";
import { renderGroupBadge } from "../ui/groups.js";
import { renderUserIdentity, userDisplayName, userIdentityText } from "../ui/identity.js";
import { setStatus } from "../ui/status.js";
import { setUsersFilterUrl, usersFilterFromSearch } from "./navigation.js";
import { formatDateTime, passesFilter } from "./shared.js";

function titleCaseRole(role) {
  const value = String(role || "reader").trim().toLowerCase();
  if (value === "librarian") return "Librarian";
  if (value === "manager") return "Manager";
  return "Reader";
}

function userSortName(user) {
  return userDisplayName(user) || String(user && user.username ? user.username : "");
}

function roleSortValue(user) {
  if (user && user.is_owner === true) return 3;
  const role = String((user && user.role) || "reader").toLowerCase();
  if (role === "manager") return 2;
  if (role === "librarian") return 1;
  return 0;
}

function lastLoginTime(user) {
  if (!user || !user.last_login) return null;
  const value = new Date(user.last_login).getTime();
  return Number.isNaN(value) ? null : value;
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

  const allowed = canManageUsers(me);
  const groupUiEnabled = advancedLibraryGroupsEnabled();

  visible(notAllowedEl, !allowed);
  visible(createLink, allowed);
  visible(filtersEl, allowed);

  let nextUrl = null;
  let prevUrl = null;
  let currentUrl = "/api/v1/accounts/users/";
  let currentResults = [];
  let totalUsersCount = null;
  let activeFilter = "all";
  let sortKey = "role";
  let sortDirection = "desc";

  const sortLabels = {
    name: "Name",
    username: "Username",
    email: "Email",
    role: "Role",
    last_login: "Last Login",
  };

  function sortButton(key) {
    const label = sortLabels[key] || key;
    const active = sortKey === key;
    const directionText = active
      ? sortDirection === "asc"
        ? "sorted ascending"
        : "sorted descending"
      : "not sorted";
    const visibleDirection = active ? (sortDirection === "asc" ? "arrow_upward" : "arrow_downward") : "unfold_more";
    return `<button class="user-sort-button" type="button" data-sort="${escapeHtml(key)}" aria-sort="${escapeHtml(active ? (sortDirection === "asc" ? "ascending" : "descending") : "none")}" aria-label="Sort by ${escapeHtml(label)}; ${escapeHtml(directionText)}">${escapeHtml(label)} <span class="material-symbols-outlined user-sort-button__icon" aria-hidden="true">${visibleDirection}</span><span class="sr-only"> ${escapeHtml(directionText)}</span></button>`;
  }

  function renderHeader() {
    return `
      <div class="users-header" aria-label="User columns">
        <div class="users-header__identity">
          ${sortButton("name")}
          ${sortButton("username")}
          ${sortButton("email")}
        </div>
        <div class="users-header__role">${sortButton("role")}</div>
        <div class="users-header__last-login">${sortButton("last_login")}</div>
        ${groupUiEnabled ? '<div class="users-header__memberships">Groups / Curates</div>' : ""}
        <div class="users-header__actions">Actions</div>
      </div>
    `.trim();
  }

  function compareText(a, b) {
    return String(a || "").localeCompare(String(b || ""), undefined, {
      sensitivity: "base",
      numeric: true,
    });
  }

  function sortedUsers(users) {
    const rows = [...users];
    if (!sortKey) return rows;
    rows.sort((a, b) => {
      let result = 0;
      if (sortKey === "name") {
        result = compareText(userSortName(a), userSortName(b));
      } else if (sortKey === "username") {
        result = compareText(a && a.username, b && b.username);
      } else if (sortKey === "email") {
        result = compareText(a && a.email, b && b.email);
      } else if (sortKey === "role") {
        result = roleSortValue(a) - roleSortValue(b);
      } else if (sortKey === "last_login") {
        const left = lastLoginTime(a);
        const right = lastLoginTime(b);
        if (left == null && right == null) result = 0;
        else if (left == null) result = 1;
        else if (right == null) result = -1;
        else result = left - right;
      }
      return sortDirection === "desc" && sortKey !== "last_login"
        ? -result
        : sortDirection === "desc" && sortKey === "last_login" && lastLoginTime(a) != null && lastLoginTime(b) != null
          ? -result
          : result;
    });
    return rows;
  }

  function updateStatusLabel() {
    if (!allowed) return;
    const total = totalUsersCount != null ? Number(totalUsersCount) : null;
    const pageCount = Array.isArray(currentResults) ? currentResults.length : 0;
    const filteredCount = (currentResults || []).filter((u) => passesFilter(u, activeFilter)).length;
    if (total != null && activeFilter && activeFilter !== "all") {
      setStatus(statusEl, `Showing ${filteredCount} filtered users on this page. Total users: ${total}.`, false);
    } else if (total != null) {
      setStatus(statusEl, `Showing ${pageCount} of ${total}.`, false);
    } else {
      setStatus(statusEl, "", false);
    }
  }

  function setActiveFilter(filter, { writeUrl = false } = {}) {
    activeFilter = filter || "all";
    const buttons = filtersEl.querySelectorAll("button[data-filter]");
    for (const btn of buttons) {
      const isActive = btn.getAttribute("data-filter") === activeFilter;
      btn.setAttribute("aria-pressed", isActive ? "true" : "false");
    }
    if (writeUrl) setUsersFilterUrl(activeFilter);
    render();
    updateStatusLabel();
  }

  function renderRow(user) {
    const profileId = user && user.profile_id != null ? String(user.profile_id) : "";
    const email = user.email || "";
    const role = user.role || "reader";
    const isOwner = !!user.is_owner;
    const isActive = user.is_active !== false;
    const lastLogin = user.last_login ? formatDateTime(user.last_login) : "";

    const roleBadge = isOwner
      ? '<span class="pill pill--owner">Owner</span>'
      : `<span class="pill">${escapeHtml(titleCaseRole(role))}</span>`;
    const inactiveBadge = isActive ? "" : '<span class="pill">inactive</span>';

    const groups = groupUiEnabled && Array.isArray(user && user.groups) ? user.groups : [];
    const memberGroupBadges = groups
      .map((group) =>
        renderGroupBadge(group, { compact: true }).outerHTML
      )
      .join(" ");
    const groupsLine = memberGroupBadges
      ? `<div class="user-row__badge-list">${memberGroupBadges}</div>`
      : `<div class="user-row__line muted">(none)</div>`;
    const curatedGroupBadges = groups
      .filter(
        (group) => group && group.is_curator === true
      )
      .map((group) =>
        renderGroupBadge(group, { compact: true }).outerHTML
      )
      .join(" ");
    const curatesLine = curatedGroupBadges
      ? `<div class="user-row__badge-list">${curatedGroupBadges}</div>`
      : `<div class="user-row__line muted">(none)</div>`;

    const lastLoginLine = lastLogin
      ? `<div class="user-row__line">${escapeHtml(lastLogin)}</div>`
      : '<div class="user-row__line muted">(never)</div>';

    const editHref = profileId ? `/users/${encodeURIComponent(String(profileId))}/edit/` : "#";
    const identityMarkup = renderUserIdentity(user, {
      includeEmail: true,
    }).outerHTML;
    const editLabel = `Edit ${userIdentityText(user, { includeEmail: true })}`;

    return `
      <article class="user-row">
        <div class="user-row__identity">
          ${identityMarkup}
          ${email ? "" : '<div class="user-row__line muted">(no email)</div>'}
        </div>
        <div class="user-row__role">
          ${roleBadge}
          ${inactiveBadge}
        </div>
        <div class="user-row__last-login">
          ${lastLoginLine}
        </div>
        ${groupUiEnabled ? `<div class="user-row__memberships">
          <div class="user-row__membership-block">
            ${groupsLine}
          </div>
          <div class="user-row__membership-block">
            ${curatesLine}
          </div>
        </div>` : ""}
        <div class="user-row__actions">
          <a class="icon-button" href="${escapeHtml(editHref)}" aria-label="${escapeHtml(editLabel)}" title="${escapeHtml(editLabel)}"><span class="material-symbols-outlined" aria-hidden="true">edit</span></a>
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
    const sorted = sortedUsers(filtered);
    resultsEl.innerHTML = `${renderHeader()}${sorted.map(renderRow).join("")}`;
  }

  async function load(url) {
    setGlobalError("");
    setStatus(statusEl, "Loading users...", false);
    resultsEl.innerHTML = "";
    nextBtn.disabled = true;
    prevBtn.disabled = true;

    currentUrl = url;

    if (!allowed) {
      setStatus(statusEl, "Not allowed.", true);
      return;
    }

    try {
      const payload = await fetchJSON(url);
      const results = Array.isArray(payload && payload.results) ? payload.results : [];
      currentResults = results;
      totalUsersCount = payload && payload.count != null ? payload.count : null;

      if (results.length === 0) {
        setStatus(statusEl, "No users.", false);
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
      setStatus(statusEl, "Error loading users.", true);
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
    setActiveFilter(filter, { writeUrl: true });
  });

  resultsEl.addEventListener("click", (e) => {
    const source = e.target;
    if (!source || source.nodeType !== 1) return;
    const target = source.closest("button[data-sort]");
    if (!target || !resultsEl.contains(target)) return;
    const nextSort = target.getAttribute("data-sort") || "";
    if (!nextSort) return;
    if (sortKey === nextSort) {
      sortDirection = sortDirection === "asc" ? "desc" : "asc";
    } else {
      sortKey = nextSort;
      sortDirection = "asc";
    }
    render();
  });

  setActiveFilter(usersFilterFromSearch());
  await load(currentUrl);

  window.addEventListener("popstate", () => {
    setActiveFilter(usersFilterFromSearch());
  });

  nextBtn.addEventListener("click", async () => {
    if (nextUrl) await load(nextUrl);
  });
  prevBtn.addEventListener("click", async () => {
    if (prevUrl) await load(prevUrl);
  });
}
