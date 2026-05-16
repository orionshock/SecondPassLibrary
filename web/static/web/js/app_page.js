import { $, loadMeAndInitShell, setText } from "./layout.js";

function clear(node) {
  if (!node) return;
  while (node.firstChild) node.removeChild(node.firstChild);
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
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
  return false;
}

function navShouldShowServerSettings(me) {
  if (!me) return false;
  return !!me.is_owner;
}

function sectionLinksForMe(me) {
  const caps = me && me.capabilities ? me.capabilities : {};
  const sections = [{ href: "/library/", label: "Library", visible: true }];
  sections.push({ href: "/groups/", label: "Groups", visible: navShouldShowGroups(me) });
  sections.push({ href: "/imports/", label: "Imports", visible: !!caps.can_access_imports });
  sections.push({ href: "/users/", label: "Users", visible: !!caps.can_manage_users });
  sections.push({
    href: "/server/",
    label: "Server settings",
    visible: navShouldShowServerSettings(me),
  });
  return sections.filter((s) => s.visible);
}

export async function initDashboard() {
  const me = await loadMeAndInitShell();
  const greetingEl = $("#app-greeting");
  const sectionsEl = $("#app-sections");
  if (!greetingEl || !sectionsEl) return;

  if (!me) {
    setText(greetingEl, "Error loading identity.");
    setText(sectionsEl, "Error loading identity.");
    return;
  }

  setText(greetingEl, `Hi, ${me.username || "User"}.`);

  clear(sectionsEl);
  const sections = sectionLinksForMe(me);
  if (!sections.length) {
    sectionsEl.appendChild(el("div", "muted", "No sections."));
    return;
  }

  for (const s of sections) {
    const a = el("a", "button", s.label);
    a.setAttribute("href", s.href);
    sectionsEl.appendChild(a);
    sectionsEl.appendChild(document.createTextNode(" "));
  }
}
