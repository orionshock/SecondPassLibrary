import { setBreadcrumbs } from "../ui/breadcrumbs.js";
import { initTabs } from "../ui/tabs.js";

const GROUP_VIEW_TABS = new Set(["books", "members", "shelves"]);
const GROUP_EDIT_TABS = new Set(["details", "books", "add-books", "members", "shelves"]);

export function groupViewTabFromSearch(search = window.location.search) {
  const params = new URLSearchParams(search || "");
  const view = (params.get("view") || "books").trim().toLowerCase();
  return GROUP_VIEW_TABS.has(view) ? view : "books";
}

export function groupEditTabFromSearch(search = window.location.search) {
  const params = new URLSearchParams(search || "");
  const view = (params.get("view") || "details").trim().toLowerCase();
  return GROUP_EDIT_TABS.has(view) ? view : "details";
}

export function groupViewHref(groupId, tab = "books") {
  const base = `/groups/${encodeURIComponent(String(groupId))}/`;
  return tab && tab !== "books" ? `${base}?view=${encodeURIComponent(String(tab))}` : base;
}

export function groupEditHref(groupId, tab = "details") {
  const base = `/groups/${encodeURIComponent(String(groupId))}/edit/`;
  return tab && tab !== "details" ? `${base}?view=${encodeURIComponent(String(tab))}` : base;
}

export function setGroupViewUrl(groupId, tab, { replace = false, resetPage = false } = {}) {
  let href = groupTabHref(groupViewHref(groupId, tab), tab, "books");
  if (resetPage) {
    const url = new URL(href, window.location.origin);
    url.searchParams.delete("page");
    href = `${url.pathname}${url.search}`;
  }
  if (replace) window.history.replaceState({}, "", href);
  else window.history.pushState({}, "", href);
}

export function setGroupEditUrl(groupId, tab, { replace = false } = {}) {
  const href = groupTabHref(groupEditHref(groupId, tab), tab, "details");
  if (replace) window.history.replaceState({}, "", href);
  else window.history.pushState({}, "", href);
}

function groupTabHref(fallbackHref, tab, defaultTab) {
  const current = new URL(window.location.href);
  const fallback = new URL(fallbackHref, current.origin);
  current.pathname = fallback.pathname;
  if (tab && tab !== defaultTab) current.searchParams.set("view", String(tab));
  else current.searchParams.delete("view");
  return `${current.pathname}${current.search}`;
}

export function selectGroupViewTab(root, tab) {
  const nextTab = GROUP_VIEW_TABS.has(tab) ? tab : "books";
  selectTab(root, nextTab);
}

export function selectGroupEditTab(root, tab) {
  const nextTab = GROUP_EDIT_TABS.has(tab) ? tab : "details";
  selectTab(root, nextTab);
}

function selectTab(root, nextTab) {
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

export function initGroupEditNavigation(root, groupId) {
  const initialTab = groupEditTabFromSearch();
  initTabs(root, { defaultTab: initialTab });
  selectGroupEditTab(root, initialTab);

  root.addEventListener("click", (event) => {
    const source = event.target;
    if (!(source instanceof Element)) return;
    const tab = source.closest(".tab-button[data-tab]");
    if (!tab || !root.contains(tab)) return;
    setGroupEditUrl(groupId, tab.getAttribute("data-tab") || "details");
  });

  window.addEventListener("popstate", () => {
    selectGroupEditTab(root, groupEditTabFromSearch());
  });
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
