import { setBreadcrumbs } from "../ui/breadcrumbs.js";
import { initTabs } from "../ui/tabs.js";

const SHELF_EDIT_TABS = new Set(["books", "add", "details"]);

export function shelfEditTabFromSearch(search = window.location.search) {
  const params = new URLSearchParams(search || "");
  const view = (params.get("view") || "books").trim().toLowerCase();
  return SHELF_EDIT_TABS.has(view) ? view : "books";
}

export function shelfEditHref(shelfId, tab = "books") {
  const base = `/shelves/${encodeURIComponent(String(shelfId))}/edit/`;
  return tab && tab !== "books" ? `${base}?view=${encodeURIComponent(String(tab))}` : base;
}

export function setShelfEditUrl(shelfId, tab, { replace = false } = {}) {
  const href = shelfEditHref(shelfId, tab);
  if (replace) window.history.replaceState({}, "", href);
  else window.history.pushState({}, "", href);
}

export function selectShelfEditTab(root, tab) {
  const nextTab = SHELF_EDIT_TABS.has(tab) ? tab : "books";
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

export function initShelfEditNavigation(root, shelfId) {
  const initialTab = shelfEditTabFromSearch();
  initTabs(root, { defaultTab: initialTab });
  selectShelfEditTab(root, initialTab);

  root.addEventListener("click", (event) => {
    const source = event.target;
    if (!(source instanceof Element)) return;
    const tab = source.closest(".tab-button[data-tab]");
    if (!tab || !root.contains(tab)) return;
    setShelfEditUrl(shelfId, tab.getAttribute("data-tab") || "books");
  });

  window.addEventListener("popstate", () => {
    selectShelfEditTab(root, shelfEditTabFromSearch());
  });
}

export function syncShelfBreadcrumb({ shelfName = "Shelf" } = {}) {
  setBreadcrumbs([
    { label: "Shelves", href: "/shelves/" },
    { label: shelfName || "Shelf", current: true },
  ]);
}

export function syncShelfEditBreadcrumb({ shelfId, shelfName = "Shelf" } = {}) {
  setBreadcrumbs([
    { label: "Shelves", href: "/shelves/" },
    {
      label: shelfName || "Shelf",
      href: shelfId ? `/shelves/${encodeURIComponent(String(shelfId))}/` : "/shelves/",
    },
    { label: "Edit", current: true },
  ]);
}
