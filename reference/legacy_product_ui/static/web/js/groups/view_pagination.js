const DEFAULT_PAGE_SIZE = 20;
const PAGE_SIZES = new Set([20, 30, 40, 50]);

function positiveInt(value, fallback) {
  const parsed = Number.parseInt(String(value || ""), 10);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

export function groupViewPageState(search = window.location.search) {
  const params = new URLSearchParams(search || "");
  const requestedSize = positiveInt(params.get("page_size"), DEFAULT_PAGE_SIZE);
  return {
    page: positiveInt(params.get("page"), 1),
    pageSize: PAGE_SIZES.has(requestedSize) ? requestedSize : DEFAULT_PAGE_SIZE,
  };
}

export function groupViewPagedApiUrl(base, search = window.location.search) {
  const state = groupViewPageState(search);
  const url = new URL(base, window.location.origin);
  url.searchParams.set("page_size", String(state.pageSize));
  if (state.page > 1) url.searchParams.set("page", String(state.page));
  else url.searchParams.delete("page");
  return `${url.pathname}${url.search}`;
}

export function groupViewRangeText(payload, resultLength, url) {
  const state = groupViewPageState(new URL(url, window.location.origin).search);
  const count = Number.isFinite(Number(payload && payload.count))
    ? Number(payload.count)
    : resultLength;
  if (!count || !resultLength) return "Showing 0 of 0";
  const start = (state.page - 1) * state.pageSize + 1;
  const end = Math.min(count, start + resultLength - 1);
  return `Showing ${start}-${end} of ${count}`;
}

export function syncGroupViewPageUrl(tab, url, { replace = false } = {}) {
  const state = groupViewPageState(new URL(url, window.location.origin).search);
  const current = new URL(window.location.href);
  if (tab === "books") current.searchParams.delete("view");
  else current.searchParams.set("view", tab);
  if (state.page > 1) current.searchParams.set("page", String(state.page));
  else current.searchParams.delete("page");
  if (state.pageSize !== DEFAULT_PAGE_SIZE) {
    current.searchParams.set("page_size", String(state.pageSize));
  } else {
    current.searchParams.delete("page_size");
  }
  const href = `${current.pathname}${current.search}`;
  if (replace) window.history.replaceState({}, "", href);
  else window.history.pushState({}, "", href);
}

export function groupViewPageSizeSearch(pageSize, search = window.location.search) {
  const requested = positiveInt(pageSize, DEFAULT_PAGE_SIZE);
  const nextSize = PAGE_SIZES.has(requested) ? requested : DEFAULT_PAGE_SIZE;
  const params = new URLSearchParams(search || "");
  params.delete("page");
  if (nextSize === DEFAULT_PAGE_SIZE) params.delete("page_size");
  else params.set("page_size", String(nextSize));
  return params.toString() ? `?${params.toString()}` : "";
}
