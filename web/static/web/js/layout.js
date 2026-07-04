import { fetchJSON } from "./api.js";
import { canAccessImports, canManageUsers, canShowGroupsNav, isOwner } from "./auth.js";
import { renderUserIdentity } from "./ui/identity.js";

let headerResizeObserver = null;

export function $(selector, root) {
  return (root || document).querySelector(selector);
}

export function setText(el, text) {
  if (!el) return;
  el.textContent = text;
}

export function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function visible(el, on) {
  if (!el) return;
  el.classList.toggle("is-hidden", !on);
}

export function advancedLibraryGroupsEnabled() {
  const value = document.body && document.body.dataset
    ? document.body.dataset.advancedLibraryGroups
    : "";
  return value === "true";
}

export function setGlobalError(message) {
  const el = $("#ui-global-error");
  if (!el) return;
  el.textContent = message || "";
  el.classList.toggle("is-hidden", !message);
}

export function setGlobalErrorFromError(error, prefix) {
  const message = error && error.message ? String(error.message) : "Unknown error.";
  setGlobalError(prefix ? `${prefix} ${message}` : message);
}

export function initAppHeaderLayout() {
  const header = $(".topbar");
  if (!header) return;

  const updateHeaderHeight = () => {
    const height = Math.ceil(header.getBoundingClientRect().height);
    if (height > 0) {
      document.documentElement.style.setProperty(
        "--app-header-height",
        `${height}px`
      );
    }
  };

  updateHeaderHeight();
  if (typeof ResizeObserver === "function") {
    if (headerResizeObserver) headerResizeObserver.disconnect();
    headerResizeObserver = new ResizeObserver(updateHeaderHeight);
    headerResizeObserver.observe(header);
  } else {
    window.addEventListener("resize", updateHeaderHeight);
  }
}

function navShouldShowGroups(me) {
  return canShowGroupsNav(me);
}

function navShouldShowAdmin(me) {
  return false;
}

function navShouldShowServerSettings(me) {
  return isOwner(me);
}

function updateNavVisibility(me) {
  visible($('[data-nav="groups"]'), navShouldShowGroups(me));
  visible($('[data-nav="imports"]'), canAccessImports(me));
  visible($('[data-nav="users"]'), canManageUsers(me));
  visible($('[data-nav="server-settings"]'), navShouldShowServerSettings(me));
}

function setActiveNav() {
  const path = window.location.pathname || "/";
  const mapping = [
    { key: "marginalia", prefix: "/reading/" },
    { key: "library", prefix: "/library/" },
    { key: "dashboard", prefix: "/dashboard/" },
    { key: "shelves", prefix: "/shelves/" },
    { key: "groups", prefix: "/groups/" },
    { key: "imports", prefix: "/imports/" },
    { key: "users", prefix: "/users/" },
    { key: "server-settings", prefix: "/server/" },
  ];
  for (const { key, prefix } of mapping) {
    const el = $(`[data-nav="${key}"]`);
    if (!el) continue;
    const on = path === prefix || path.startsWith(prefix);
    if (on) el.setAttribute("aria-current", "page");
    else el.removeAttribute("aria-current");
  }
}

export async function loadMeAndInitShell() {
  setActiveNav();

  try {
    const me = await fetchJSON("/api/v1/accounts/me/");
    const identityTarget = $('[data-ui="username"]');
    if (identityTarget) {
      identityTarget.replaceChildren(
        renderUserIdentity(me, {
          className: "user-identity--shell",
          includeDisplayName: false,
        })
      );
    }
    updateNavVisibility(me);
    return me;
  } catch (e) {
    console.error("Failed to load /api/v1/accounts/me/", e);
    setText($('[data-ui="username"]'), "Error");
    setGlobalErrorFromError(e, "Failed to load identity:");
    return null;
  }
}
