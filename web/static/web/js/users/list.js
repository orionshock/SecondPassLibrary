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
import { renderUserIdentity, userIdentityText } from "../ui/identity.js";
import { setStatus } from "../ui/status.js";
import { formatDateTime } from "./shared.js";

const DEFAULT_PAGE_SIZE = 20;
const PAGE_SIZE_OPTIONS = new Set([20, 30, 40, 50]);
const ROLES = new Set(["owner", "manager", "librarian", "reader", "curator"]);
const ACTIVE_FILTERS = new Set(["true", "false"]);
const ORDERINGS = new Set([
  "username", "-username", "name", "-name", "role", "-role", "is_active", "-is_active",
]);

function normalizedPageSize(value) {
  const parsed = Number.parseInt(String(value || ""), 10);
  return PAGE_SIZE_OPTIONS.has(parsed) ? parsed : DEFAULT_PAGE_SIZE;
}

export function usersListState(search = "") {
  const params = new URLSearchParams(search || "");
  const role = String(params.get("role") || "").toLowerCase();
  const isActive = String(params.get("is_active") || "").toLowerCase();
  const ordering = String(params.get("ordering") || "username").toLowerCase();
  const rawPage = Number.parseInt(params.get("page") || "1", 10);
  return {
    q: String(params.get("q") || "").trim(),
    role: ROLES.has(role) ? role : "",
    isActive: ACTIVE_FILTERS.has(isActive) ? isActive : "",
    ordering: ORDERINGS.has(ordering) ? ordering : "username",
    page: Number.isInteger(rawPage) && rawPage > 0 ? rawPage : 1,
    pageSize: normalizedPageSize(params.get("page_size")),
  };
}

function stateParams(state, { includeDefaults = false } = {}) {
  const params = new URLSearchParams();
  if (state.q) params.set("q", state.q);
  if (state.role) params.set("role", state.role);
  if (state.isActive) params.set("is_active", state.isActive);
  if (includeDefaults || state.ordering !== "username") params.set("ordering", state.ordering);
  if (includeDefaults || state.page > 1) params.set("page", String(state.page));
  if (includeDefaults || state.pageSize !== DEFAULT_PAGE_SIZE) params.set("page_size", String(state.pageSize));
  return params;
}

export function usersListHref(state) {
  const query = stateParams(state).toString();
  return query ? `/users/?${query}` : "/users/";
}

export function usersApiUrl(state) {
  return `/api/v1/accounts/users/?${stateParams(state, { includeDefaults: true }).toString()}`;
}

function titleCaseRole(role) {
  const value = String(role || "reader").trim().toLowerCase();
  if (value === "librarian") return "Librarian";
  if (value === "manager") return "Manager";
  return "Reader";
}

export async function initUsersList() {
  const me = await loadMeAndInitShell();
  setGlobalError("");

  const notAllowedEl = $("#users-not-allowed");
  const createLink = $("#users-create-link");
  const searchForm = $("#users-search");
  const searchInput = $("#users-q");
  const filtersEl = $("#users-filters");
  const activeSelect = $("#users-is-active");
  const statusEl = $("#users-status");
  const resultsEl = $("#users-results");
  const nextButtons = [$("#users-next-top"), $("#users-next-bottom")];
  const prevButtons = [$("#users-prev-top"), $("#users-prev-bottom")];
  const pageSizeSelects = [$("#users-page-size-top"), $("#users-page-size-bottom")];
  const rangeEls = [$("#users-range-top"), $("#users-range-bottom")];
  const pagers = [$("#users-pager-top"), $("#users-pager-bottom")];
  const required = [
    notAllowedEl, createLink, searchForm, searchInput, filtersEl, activeSelect, statusEl, resultsEl,
    ...nextButtons, ...prevButtons, ...pageSizeSelects, ...rangeEls, ...pagers,
  ];
  if (required.some((element) => !element)) return;

  const allowed = canManageUsers(me);
  const groupUiEnabled = advancedLibraryGroupsEnabled();
  let state = usersListState(window.location.search);
  if (!groupUiEnabled && state.role === "curator") state = { ...state, role: "", page: 1 };
  let hasNext = false;
  let hasPrevious = false;
  let totalUsersCount = 0;

  visible(notAllowedEl, !allowed);
  visible(createLink, allowed);
  visible(searchForm, allowed);
  visible(filtersEl, allowed);
  visible(activeSelect.closest("label"), allowed);

  function orderingParts() {
    const descending = state.ordering.startsWith("-");
    return { key: state.ordering.replace(/^-/, ""), descending };
  }

  function sortButton(key, label) {
    const current = orderingParts();
    const active = current.key === key;
    const direction = active && current.descending ? "descending" : active ? "ascending" : "none";
    const icon = active ? (current.descending ? "arrow_downward" : "arrow_upward") : "unfold_more";
    return `<button class="user-sort-button" type="button" data-sort="${escapeHtml(key)}" aria-sort="${direction}" aria-label="Sort by ${escapeHtml(label)}">${escapeHtml(label)} <span class="material-symbols-outlined user-sort-button__icon" aria-hidden="true">${icon}</span></button>`;
  }

  function renderHeader() {
    return `
      <div class="users-header" aria-label="User columns">
        <div class="users-header__identity">
          ${sortButton("name", "Name")}
          ${sortButton("username", "Username")}
          <span>Email</span>
        </div>
        <div class="users-header__role">${sortButton("role", "Role")} ${sortButton("is_active", "Status")}</div>
        <div class="users-header__last-login">Last Login</div>
        ${groupUiEnabled ? '<div class="users-header__memberships">Groups / Curates</div>' : ""}
        <div class="users-header__actions">Actions</div>
      </div>
    `.trim();
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
    const inactiveBadge = isActive ? "" : '<span class="pill pill--inactive">Inactive</span>';
    const groups = groupUiEnabled && Array.isArray(user && user.groups) ? user.groups : [];
    const badges = (items) => items.map((group) => renderGroupBadge(group, { compact: true }).outerHTML).join(" ");
    const groupsLine = badges(groups) || '<span class="muted">(none)</span>';
    const curatesLine = badges(groups.filter((group) => group && group.is_curator === true)) || '<span class="muted">(none)</span>';
    const editHref = profileId ? `/users/${encodeURIComponent(profileId)}/edit/` : "#";
    const identityMarkup = renderUserIdentity(user, { includeEmail: true }).outerHTML;
    const editLabel = `Edit ${userIdentityText(user, { includeEmail: true })}`;
    return `
      <article class="user-row${isActive ? "" : " user-row--inactive"}">
        <div class="user-row__identity">${identityMarkup}${email ? "" : '<div class="user-row__line muted">(no email)</div>'}</div>
        <div class="user-row__role">${roleBadge}${inactiveBadge}</div>
        <div class="user-row__last-login"><div class="user-row__line${lastLogin ? "" : " muted"}">${escapeHtml(lastLogin || "(never)")}</div></div>
        ${groupUiEnabled ? `<div class="user-row__memberships"><div class="user-row__badge-list">${groupsLine}</div><div class="user-row__badge-list">${curatesLine}</div></div>` : ""}
        <div class="user-row__actions"><a class="icon-button" href="${escapeHtml(editHref)}" aria-label="${escapeHtml(editLabel)}" title="${escapeHtml(editLabel)}"><span class="material-symbols-outlined" aria-hidden="true">edit</span></a></div>
      </article>
    `.trim();
  }

  function syncControls() {
    searchInput.value = state.q;
    activeSelect.value = state.isActive;
    filtersEl.querySelectorAll("button[data-filter]").forEach((button) => {
      const value = button.getAttribute("data-filter") || "all";
      button.setAttribute("aria-pressed", (value === "all" ? !state.role : value === state.role) ? "true" : "false");
    });
    pageSizeSelects.forEach((select) => { select.value = String(state.pageSize); });
  }

  function syncPager(resultCount) {
    const start = totalUsersCount && resultCount ? (state.page - 1) * state.pageSize + 1 : 0;
    const range = start ? `Showing ${start}-${Math.min(totalUsersCount, start + resultCount - 1)} of ${totalUsersCount}` : "Showing 0 of 0";
    rangeEls.forEach((element) => { element.textContent = range; });
    nextButtons.forEach((button) => { button.disabled = !hasNext; });
    prevButtons.forEach((button) => { button.disabled = !hasPrevious; });
    pagers.forEach((pager) => pager.classList.toggle("is-hidden", totalUsersCount === 0));
  }

  function writeState({ replace = false } = {}) {
    const href = usersListHref(state);
    if (replace) window.history.replaceState({}, "", href);
    else window.history.pushState({}, "", href);
  }

  async function load() {
    setGlobalError("");
    setStatus(statusEl, "Loading users...", false);
    resultsEl.replaceChildren();
    if (!allowed) {
      setStatus(statusEl, "Not allowed.", true);
      return;
    }
    try {
      const payload = await fetchJSON(usersApiUrl(state));
      const results = Array.isArray(payload && payload.results) ? payload.results : [];
      totalUsersCount = Number(payload && payload.count) || 0;
      hasNext = !!(payload && payload.next);
      hasPrevious = !!(payload && payload.previous);
      resultsEl.innerHTML = results.length
        ? `${renderHeader()}${results.map(renderRow).join("")}`
        : '<div class="muted">No users.</div>';
      setStatus(statusEl, "", false);
      syncPager(results.length);
      syncControls();
    } catch (error) {
      hasNext = false;
      hasPrevious = false;
      setStatus(statusEl, "Error loading users.", true);
      setGlobalError(String(extractApiErrorMessage(error) || "Failed to load users.").slice(0, 240));
      syncPager(0);
    }
  }

  async function changeState(changes) {
    state = { ...state, ...changes, page: 1 };
    writeState();
    await load();
  }

  searchForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await changeState({ q: searchInput.value.trim() });
  });
  filtersEl.addEventListener("click", async (event) => {
    const source = event.target;
    if (!(source instanceof Element)) return;
    const button = source.closest("button[data-filter]");
    if (!button) return;
    const role = button.getAttribute("data-filter") || "";
    await changeState({ role: role === "all" ? "" : role });
  });
  activeSelect.addEventListener("change", async () => {
    await changeState({ isActive: activeSelect.value });
  });
  resultsEl.addEventListener("click", async (event) => {
    const source = event.target;
    if (!(source instanceof Element)) return;
    const button = source.closest("button[data-sort]");
    if (!button) return;
    const key = button.getAttribute("data-sort") || "username";
    const current = orderingParts();
    await changeState({ ordering: current.key === key && !current.descending ? `-${key}` : key });
  });
  nextButtons.forEach((button) => button.addEventListener("click", async () => {
    if (!hasNext) return;
    state = { ...state, page: state.page + 1 };
    writeState();
    await load();
  }));
  prevButtons.forEach((button) => button.addEventListener("click", async () => {
    if (!hasPrevious) return;
    state = { ...state, page: Math.max(1, state.page - 1) };
    writeState();
    await load();
  }));
  pageSizeSelects.forEach((select) => select.addEventListener("change", async () => {
    await changeState({ pageSize: normalizedPageSize(select.value) });
  }));
  window.addEventListener("popstate", async () => {
    state = usersListState(window.location.search);
    await load();
  });

  writeState({ replace: true });
  syncControls();
  await load();
}
