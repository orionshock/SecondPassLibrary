import { setBreadcrumbs } from "../ui/breadcrumbs.js";

const GROUP_VIEW_TABS = new Set(["books", "members", "shelves"]);

export function groupViewTabFromSearch(search = window.location.search) {
  const params = new URLSearchParams(search || "");
  const view = (params.get("view") || "books").trim().toLowerCase();
  return GROUP_VIEW_TABS.has(view) ? view : "books";
}

export function groupViewHref(groupId, tab = "books") {
  const base = `/groups/${encodeURIComponent(String(groupId))}/`;
  return tab && tab !== "books" ? `${base}?view=${encodeURIComponent(String(tab))}` : base;
}

export function setGroupViewUrl(groupId, tab, { replace = false } = {}) {
  const href = groupViewHref(groupId, tab);
  if (replace) window.history.replaceState({}, "", href);
  else window.history.pushState({}, "", href);
}

export function selectGroupViewTab(root, tab) {
  const nextTab = GROUP_VIEW_TABS.has(tab) ? tab : "books";
  const buttons = Array.from(root.querySelectorAll(".tab-button[data-tab]"));
  const panels = Array.from(root.querySelectorAll("[data-tab-panel]"));

  for (const panel of panels) {
    const isActive = panel.getAttribute("data-tab-panel") === nextTab;
    panel.classList.toggle("is-hidden", !isActive);
    if (panel.getAttribute("role") === "tabpanel") {
      panel.setAttribute("aria-hidden", isActive ? "false" : "true");
    }
  }

  for (const button of buttons) {
    const isActive = button.getAttribute("data-tab") === nextTab;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-selected", isActive ? "true" : "false");
  }
}

export function syncGroupBreadcrumb({ groupName = "Group" } = {}) {
  setBreadcrumbs([
    { label: "Groups", href: "/groups/" },
    { label: groupName || "Group", current: true },
  ]);
}

export function syncGroupEditBreadcrumb({ groupId, groupName = "Group" } = {}) {
  setBreadcrumbs([
    { label: "Groups", href: "/groups/" },
    {
      label: groupName || "Group",
      href: groupId ? `/groups/${encodeURIComponent(String(groupId))}/` : "/groups/",
    },
    { label: "Edit", current: true },
  ]);
}
