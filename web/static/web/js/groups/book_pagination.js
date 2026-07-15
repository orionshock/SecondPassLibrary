const BOOK_FILTER_PARAMS = ["q", "ordering", "tag", "author", "series", "publisher", "page_size"];

export function groupBooksApiUrl(groupId, search = window.location.search) {
  const source = new URLSearchParams(search || "");
  const target = new URLSearchParams();
  for (const key of BOOK_FILTER_PARAMS) {
    const value = source.get(key);
    if (value) target.set(key, value);
  }
  const page = Number.parseInt(source.get("page") || "1", 10);
  if (Number.isInteger(page) && page > 1) target.set("page", String(page));
  const query = target.toString();
  const base = `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/books/`;
  return query ? `${base}?${query}` : base;
}

export function groupBookPageStatus(payload, results, url) {
  const page = pageFromUrl(url);
  const count = Number.isFinite(Number(payload && payload.count)) ? Number(payload.count) : null;
  if (!results.length) return page > 1 ? `Page ${page}. No books.` : "No books in this group.";
  return count == null
    ? `Page ${page}. Showing ${results.length}.`
    : `Page ${page}. Showing ${results.length} of ${count}.`;
}

export function syncGroupBookPage(url, { replace = false } = {}) {
  const page = pageFromUrl(url);
  const current = new URL(window.location.href);
  if (page > 1) current.searchParams.set("page", String(page));
  else current.searchParams.delete("page");
  const href = `${current.pathname}${current.search}`;
  if (replace) window.history.replaceState({}, "", href);
  else window.history.pushState({}, "", href);
}

function pageFromUrl(url) {
  try {
    const page = Number.parseInt(new URL(url, window.location.origin).searchParams.get("page") || "1", 10);
    return Number.isInteger(page) && page > 0 ? page : 1;
  } catch {
    return 1;
  }
}
