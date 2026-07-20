import { initTabs } from "../ui/tabs.js";

const QUERY_TO_PANEL = {
  book: "book-details",
  catalog: "catalog",
  "authors-series": "authors",
  groups: "groups",
  shelves: "shelves",
  "identifiers-file": "idents",
};
const PANEL_TO_QUERY = Object.fromEntries(
  Object.entries(QUERY_TO_PANEL).map(([query, panel]) => [panel, query])
);

export function bookEditTabFromSearch(search = window.location.search) {
  const value = String(new URLSearchParams(search || "").get("tab") || "book")
    .trim()
    .toLowerCase();
  return Object.hasOwn(QUERY_TO_PANEL, value) ? value : "book";
}

export function bookEditHref(tab, href = window.location.href) {
  const url = new URL(href, window.location.origin);
  const nextTab = Object.hasOwn(QUERY_TO_PANEL, tab) ? tab : "book";
  url.searchParams.set("tab", nextTab);
  return `${url.pathname}${url.search}`;
}

function availablePanel(root, queryTab) {
  const requested = QUERY_TO_PANEL[queryTab] || QUERY_TO_PANEL.book;
  return root.querySelector(`.tab-button[data-tab="${requested}"]`)
    ? requested
    : QUERY_TO_PANEL.book;
}

export function selectBookEditTab(root, queryTab) {
  const panelKey = availablePanel(root, queryTab);
  const buttons = Array.from(root.querySelectorAll(".tab-button[data-tab]"));
  const panels = Array.from(root.querySelectorAll("[data-tab-panel]"));
  for (const panel of panels) {
    const active = panel.getAttribute("data-tab-panel") === panelKey;
    panel.classList.toggle("is-hidden", !active);
    panel.setAttribute("aria-hidden", active ? "false" : "true");
  }
  for (const button of buttons) {
    const active = button.getAttribute("data-tab") === panelKey;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", active ? "true" : "false");
  }
  return PANEL_TO_QUERY[panelKey] || "book";
}

export function initBookEditNavigation(root) {
  const initialTab = bookEditTabFromSearch();
  const initialPanel = availablePanel(root, initialTab);
  initTabs(root, { defaultTab: initialPanel });
  selectBookEditTab(root, initialTab);

  root.addEventListener("click", (event) => {
    const source = event.target;
    if (!(source instanceof Element)) return;
    const button = source.closest(".tab-button[data-tab]");
    if (!button || !root.contains(button)) return;
    const queryTab = PANEL_TO_QUERY[button.getAttribute("data-tab")] || "book";
    if (queryTab === bookEditTabFromSearch()) return;
    window.history.pushState({}, "", bookEditHref(queryTab));
  });

  window.addEventListener("popstate", () => {
    selectBookEditTab(root, bookEditTabFromSearch());
  });
}
