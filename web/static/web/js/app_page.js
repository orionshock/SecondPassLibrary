import { $, escapeHtml, loadMeAndInitShell, setText } from "./layout.js";

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

function sectionLinksForMe(me) {
  const caps = me && me.capabilities ? me.capabilities : {};
  const sections = [{ href: "/library/", label: "Library", visible: true }];
  sections.push({ href: "/groups/", label: "Groups", visible: navShouldShowGroups(me) });
  sections.push({ href: "/imports/", label: "Imports", visible: !!caps.can_access_imports });
  sections.push({ href: "/users/", label: "Users", visible: !!caps.can_manage_users });
  sections.push({ href: "/admin/", label: "Service Hatch", visible: navShouldShowAdmin(me) });
  return sections.filter((s) => s.visible);
}

export async function initDashboard() {
  const me = await loadMeAndInitShell();
  if (!me) {
    setText($("#app-greeting"), "Error loading identity.");
    setText($("#app-sections"), "Error loading identity.");
    return;
  }

  const greeting = `Hi, ${escapeHtml(me.username || "User")}.`;
  $("#app-greeting").innerHTML = greeting;

  const sections = sectionLinksForMe(me)
    .map((s) => `<a class="button" href="${escapeHtml(s.href)}">${escapeHtml(s.label)}</a>`)
    .join(" ");
  $("#app-sections").innerHTML = sections || '<div class="muted">No sections.</div>';
}

