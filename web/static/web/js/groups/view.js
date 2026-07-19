import { extractApiErrorMessage, fetchJSON } from "../api.js";
import { $, loadMeAndInitShell, setGlobalError, visible } from "../layout.js";
import { createPagedListController } from "../ui/paged_list.js";
import {
  groupBooksApiUrl,
} from "./book_pagination.js";
import { setStatus } from "../ui/status.js";
import { initTabs } from "../ui/tabs.js";
import {
  groupViewTabFromSearch,
  selectGroupViewTab,
  setGroupViewUrl,
  syncGroupBreadcrumb,
} from "./navigation.js";
import {
  canEditGroupPage,
  currentUserGroupMembership,
} from "./shared.js";
import {
  renderGroupViewBooks,
  renderGroupViewMembers,
  renderGroupViewShelves,
} from "./view_renderers.js";
import {
  groupViewPagedApiUrl,
  groupViewPageSizeSearch,
  groupViewPageState,
  groupViewRangeText,
  syncGroupViewPageUrl,
} from "./view_pagination.js";

function pagerElements(tab) {
  return {
    statusEl: $(`#group-view-${tab}-status`),
    resultsEl: $(`#group-view-${tab}-results`),
    nextBtn: $(`#group-view-${tab}-next`),
    prevBtn: $(`#group-view-${tab}-prev`),
    nextTopBtn: $(`#group-view-${tab}-next-top`),
    prevTopBtn: $(`#group-view-${tab}-prev-top`),
    rangeEl: $(`#group-view-${tab}-range`),
    rangeTopEl: $(`#group-view-${tab}-range-top`),
    pageSizeEl: $(`#group-view-${tab}-page-size`),
    pageSizeTopEl: $(`#group-view-${tab}-page-size-top`),
  };
}

async function initGroupViewPager({ tab, apiUrl, emptyText, render, loadErrorText }) {
  const elements = pagerElements(tab);
  if (Object.values(elements).some((element) => !element)) return null;
  const {
    statusEl,
    resultsEl,
    nextBtn,
    prevBtn,
    nextTopBtn,
    prevTopBtn,
    rangeEl,
    rangeTopEl,
    pageSizeEl,
    pageSizeTopEl,
  } = elements;

  function syncPager(payload, results, url) {
    const state = groupViewPageState(new URL(url, window.location.origin).search);
    const range = groupViewRangeText(payload, results.length, url);
    rangeEl.textContent = range;
    rangeTopEl.textContent = range;
    pageSizeEl.value = String(state.pageSize);
    pageSizeTopEl.value = String(state.pageSize);
    nextTopBtn.disabled = nextBtn.disabled;
    prevTopBtn.disabled = prevBtn.disabled;
  }

  const controller = await createPagedListController({
    statusEl,
    resultsEl,
    nextBtn,
    prevBtn,
    initialUrl: apiUrl(window.location.search),
    emptyText,
    render,
    formatStatus: (_payload, results) => results.length ? "" : emptyText,
    onLoaded: (payload, results, context) => {
      syncPager(payload, results, context.url);
      if (["next", "previous", "page-size"].includes(context.reason)) {
        syncGroupViewPageUrl(tab, context.url);
      }
    },
    loadErrorText,
  });

  nextTopBtn.addEventListener("click", () => nextBtn.click());
  prevTopBtn.addEventListener("click", () => prevBtn.click());

  async function changePageSize(source) {
    const search = groupViewPageSizeSearch(source.value);
    pageSizeEl.value = String(groupViewPageState(search).pageSize);
    pageSizeTopEl.value = pageSizeEl.value;
    await controller.load(apiUrl(search), { reason: "page-size" });
  }
  pageSizeEl.addEventListener("change", () => changePageSize(pageSizeEl));
  pageSizeTopEl.addEventListener("change", () => changePageSize(pageSizeTopEl));

  return {
    loadFromLocation: () => controller.load(apiUrl(window.location.search), { reason: "history" }),
  };
}

export async function initGroupView() {
  const me = await loadMeAndInitShell();
  setGlobalError("");

  const root = $("#group-view-root");
  const summaryEl = $("#group-view-summary");
  const statusEl = $("#group-view-status");
  const titleEl = $("#group-view-title");
  const subtitleEl = $("#group-view-subtitle");
  const badgesEl = $("#group-view-badges");
  const descEl = $("#group-view-description");
  const editWrap = $("#group-view-edit-link-wrap");
  const editLink = $("#group-view-edit-link");

  const membersNote = $("#group-view-members-note");

  if (
    !root ||
    !summaryEl ||
    !statusEl ||
    !titleEl ||
    !subtitleEl ||
    !badgesEl ||
    !descEl ||
    !membersNote
  ) {
    return;
  }

  const groupId = root.getAttribute("data-group-id") || "";
  if (!groupId) return;
  const initialTab = groupViewTabFromSearch();
  initTabs(root, { defaultTab: initialTab });
  selectGroupViewTab(root, initialTab);
  syncGroupBreadcrumb({ groupName: "Group" });

  setStatus(statusEl, "Loading...", false);
  visible(root, false);
  visible(summaryEl, false);
  visible(editWrap, false);

  let group = null;
  try {
    group = await fetchJSON(`/api/v1/library/groups/${encodeURIComponent(String(groupId))}/`);
  } catch (e) {
    console.error("Failed to load group", { groupId, e });
    if (e && e.status === 404) setStatus(statusEl, "Not found or not accessible.", true);
    else if (e && e.status === 403) setStatus(statusEl, "Permission denied.", true);
    else setStatus(statusEl, "Error loading group.", true);
    setGlobalError(extractApiErrorMessage(e));
    return;
  }

  const isPublicGroup = !!group.is_public_group;
  titleEl.textContent = group.name || "Group";
  syncGroupBreadcrumb({ groupName: group.name || "Group" });

  subtitleEl.textContent = "";

  if (canEditGroupPage({ me, group })) {
    if (editLink) editLink.setAttribute("href", `/groups/${encodeURIComponent(String(groupId))}/edit/`);
    visible(editWrap, true);
  }

  // Stable details card above tabs.
  badgesEl.textContent = "";
  const badgesNode = document.createElement("div");
  if (isPublicGroup) {
    const b = document.createElement("span");
    b.className = "pill pill--owner";
    b.textContent = "Public";
    badgesNode.appendChild(b);
  }
  const currentMembership = currentUserGroupMembership({ me, group });
  if (currentMembership && currentMembership.is_curator === true) {
    if (badgesNode.childNodes.length) badgesNode.appendChild(document.createTextNode(" "));
    const b2 = document.createElement("span");
    b2.className = "pill";
    b2.textContent = "Curator";
    badgesNode.appendChild(b2);
  }
  badgesEl.appendChild(badgesNode);
  descEl.textContent = group.description || "";

  visible(summaryEl, true);
  visible(root, true);
  setStatus(statusEl, "", false);

  const pagers = {};
  pagers.books = await initGroupViewPager({
    tab: "books",
    apiUrl: (search) => groupBooksApiUrl(groupId, search),
    emptyText: "No books in this group.",
    render: (payload) => renderGroupViewBooks(payload),
    loadErrorText: "Unable to load group books.",
  });

  membersNote.textContent = "";
  const membershipsBase = `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/`;
  pagers.members = await initGroupViewPager({
    tab: "members",
    apiUrl: (search) => groupViewPagedApiUrl(membershipsBase, search),
    emptyText: "No members.",
    render: (payload) => renderGroupViewMembers(payload),
    loadErrorText: "Unable to load group members.",
  });

  const shelvesBase = `/api/v1/shelves/?owner_group=${encodeURIComponent(String(groupId))}&include_preview_books=true`;
  pagers.shelves = await initGroupViewPager({
    tab: "shelves",
    apiUrl: (search) => groupViewPagedApiUrl(shelvesBase, search),
    emptyText: "No shelves yet.",
    render: (payload) => renderGroupViewShelves(payload),
    loadErrorText: "Unable to load group shelves.",
  });

  root.addEventListener("click", async (event) => {
    const source = event.target;
    if (!(source instanceof Element)) return;
    const tabButton = source.closest(".tab-button[data-tab]");
    if (!tabButton || !root.contains(tabButton)) return;
    const nextTab = tabButton.getAttribute("data-tab") || "books";
    if (nextTab === groupViewTabFromSearch()) return;
    setGroupViewUrl(groupId, nextTab, { resetPage: true });
    const pager = pagers[nextTab];
    if (pager) await pager.loadFromLocation();
  });

  window.addEventListener("popstate", async () => {
    const tab = groupViewTabFromSearch();
    selectGroupViewTab(root, tab);
    const pager = pagers[tab];
    if (pager) await pager.loadFromLocation();
  });
}
