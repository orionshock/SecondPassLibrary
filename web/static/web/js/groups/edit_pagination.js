import { createPagedListController } from "../ui/paged_list.js";
import { groupEditTabFromSearch } from "./navigation.js";
import {
  groupViewPageSizeSearch,
  groupViewPageState,
  groupViewPagedApiUrl,
  groupViewRangeText,
} from "./view_pagination.js";

function element(id) {
  return document.getElementById(id);
}

export function syncGroupEditPageUrl(tab, url, { replace = false } = {}) {
  const loaded = new URL(url, window.location.origin);
  const state = groupViewPageState(loaded.search);
  const current = new URL(window.location.href);
  if (tab === "details") current.searchParams.delete("view");
  else current.searchParams.set("view", tab);
  if (state.page > 1) current.searchParams.set("page", String(state.page));
  else current.searchParams.delete("page");
  if (state.pageSize === 20) current.searchParams.delete("page_size");
  else current.searchParams.set("page_size", String(state.pageSize));
  if (tab === "add-books") {
    const query = loaded.searchParams.get("q") || "";
    if (query) current.searchParams.set("q", query);
    else current.searchParams.delete("q");
  }
  const href = `${current.pathname}${current.search}`;
  if (replace) window.history.replaceState({}, "", href);
  else window.history.pushState({}, "", href);
}

export async function createGroupEditPager({
  key,
  tab,
  statusEl,
  resultsEl,
  nextBtn,
  prevBtn,
  initialUrl,
  emptyText,
  render,
  onLoaded = null,
  loadErrorText,
  autoLoad = true,
}) {
  const nextTopBtn = element(`group-edit-${key}-next-top`);
  const prevTopBtn = element(`group-edit-${key}-prev-top`);
  const rangeEl = element(`group-edit-${key}-range`);
  const rangeTopEl = element(`group-edit-${key}-range-top`);
  const pageSizeEl = element(`group-edit-${key}-page-size`);
  const pageSizeTopEl = element(`group-edit-${key}-page-size-top`);
  const controls = [nextTopBtn, prevTopBtn, rangeEl, rangeTopEl, pageSizeEl, pageSizeTopEl];
  if (controls.some((control) => !control)) return null;

  const baseUrl = (search) => typeof initialUrl === "function" ? initialUrl(search) : initialUrl;
  const urlForSearch = (search) => groupViewPagedApiUrl(baseUrl(search), search);
  function syncControls(payload, results, url) {
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
    initialUrl: urlForSearch(window.location.search),
    emptyText,
    render,
    formatStatus: (_payload, results) => results.length ? "" : emptyText,
    onLoaded: (payload, results, context) => {
      syncControls(payload, results, context.url);
      if (["next", "previous", "page-size", "search"].includes(context.reason)) {
        syncGroupEditPageUrl(tab, context.url);
      }
      if (onLoaded) onLoaded(payload, results, context);
    },
    loadErrorText,
    autoLoad,
  });

  nextTopBtn.addEventListener("click", () => nextBtn.click());
  prevTopBtn.addEventListener("click", () => prevBtn.click());
  async function changePageSize(source) {
    const search = groupViewPageSizeSearch(source.value);
    const currentUrl = controller.getState().currentUrl || baseUrl(window.location.search);
    const resizedUrl = groupViewPagedApiUrl(currentUrl, search);
    await controller.load(resizedUrl, { reason: "page-size" });
  }
  pageSizeEl.addEventListener("change", () => changePageSize(pageSizeEl));
  pageSizeTopEl.addEventListener("change", () => changePageSize(pageSizeTopEl));

  window.addEventListener("popstate", async () => {
    if (groupEditTabFromSearch() === tab) {
      await controller.load(urlForSearch(window.location.search), { reason: "history" });
    }
  });
  window.addEventListener("group-edit-tab-change", async (event) => {
    if (event.detail && event.detail.tab === tab) {
      await controller.load(urlForSearch(window.location.search), { reason: "tab" });
    }
  });
  return controller;
}
