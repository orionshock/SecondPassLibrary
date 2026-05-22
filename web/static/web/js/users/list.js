import { extractApiErrorMessage, fetchJSON } from "../api.js";
import { $, escapeHtml, loadMeAndInitShell, setGlobalError, visible } from "../layout.js";
import { curatedGroupsFromUser, formatDateTime, groupsSummary, passesFilter, setElStatus } from "./shared.js";

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
    setElStatus(statusEl, text, isError);
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
    const groupsLine = groupText
      ? `<div class="user-row__line">Groups: ${escapeHtml(groupText)}</div>`
      : `<div class="user-row__line muted">Groups: (none)</div>`;

    const lastLoginLine = lastLogin
      ? `<div class="user-row__line">Last login: ${escapeHtml(lastLogin)}</div>`
      : '<div class="user-row__line muted">Last login: (never)</div>';

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
    setStatus("Loading users...", false);
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
