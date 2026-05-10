import { fetchJSON } from "./api.js";

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

export function formatRole(role) {
  if (!role) return "";
  return role.charAt(0).toUpperCase() + role.slice(1);
}

function navShouldShowGroups(me) {
  if (!me) return false;
  const groups = Array.isArray(me.groups) ? me.groups : [];
  const caps = me.capabilities || {};
  return (
    groups.length > 0 ||
    !!caps.can_manage_library ||
    !!caps.can_create_library_groups ||
    !!caps.can_manage_group_memberships ||
    !!caps.can_manage_group_identity ||
    !!caps.can_edit_group_presentation
  );
}

function navShouldShowAdmin(me) {
  if (!me) return false;
  if (me.is_owner) return true;
  return me.role === "manager";
}

function updateNavVisibility(me) {
  const caps = me && me.capabilities ? me.capabilities : {};

  visible($('[data-nav="groups"]'), navShouldShowGroups(me));
  visible($('[data-nav="imports"]'), !!caps.can_access_imports);
  visible($('[data-nav="users"]'), !!caps.can_manage_users);
  visible($('[data-nav="admin"]'), navShouldShowAdmin(me));
}

function setActiveNav() {
  const path = window.location.pathname || "/";
  const mapping = [
    { key: "library", prefix: "/library/" },
    { key: "app", prefix: "/app/" },
    { key: "groups", prefix: "/groups/" },
    { key: "imports", prefix: "/imports/" },
    { key: "users", prefix: "/users/" },
    { key: "admin", prefix: "/admin/" },
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
    setText($('[data-ui="username"]'), me.username || "User");
    updateNavVisibility(me);
    return me;
  } catch (e) {
    console.error("Failed to load /api/v1/accounts/me/", e);
    setText($('[data-ui="username"]'), "Error");
    setGlobalErrorFromError(e, "Failed to load identity:");
    return null;
  }
}

