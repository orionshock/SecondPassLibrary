export function pathWithParams(base, params) {
  const url = new URL(base, window.location.origin);
  for (const [key, value] of Object.entries(params || {})) {
    if (value === null || value === undefined || value === "") continue;
    url.searchParams.set(key, String(value));
  }
  return `${url.pathname}${url.search}`;
}

export function libraryContextHref(context) {
  if (!context) return "";
  if (context.kind === "author" && context.id) {
    return pathWithParams(productUiPath("/library/"), {
      view: "author",
      author: context.id,
    });
  }
  if (context.kind === "series" && context.id) {
    return pathWithParams(productUiPath("/library/"), {
      view: "series",
      series: context.id,
    });
  }
  return "";
}

export function libraryBookDetailHref(bookId, context = null) {
  if (!bookId) return "";
  const base = productUiPath(`/library/books/${encodeURIComponent(String(bookId))}/`);
  if (context && (context.kind === "author" || context.kind === "series")) {
    const key = context.kind;
    return pathWithParams(base, {
      view: key,
      [key]: context.id,
    });
  }
  return pathWithParams(base, { view: "books" });
}

const LIBRARY_STATE_PARAMS = new Set(["view", "q", "page", "page_size", "author", "series"]);

export function preservedLibraryParams(searchParams) {
  const preserved = {};
  for (const [key, value] of searchParams.entries()) {
    if (!LIBRARY_STATE_PARAMS.has(key)) preserved[key] = value;
  }
  return preserved;
}

export function librarySearchPlaceholder(view, seriesId = "") {
  if (view === "authors") return "Author name...";
  if (view === "series" && !seriesId) return "Series name...";
  return "Book title...";
}

export function libraryParamsForTagSelection(preservedParams, slug) {
  const params = { ...(preservedParams || {}) };
  const cleanSlug = String(slug || "").trim();
  if (cleanSlug) params.tag = cleanSlug;
  else delete params.tag;
  return params;
}

export function canonicalLibraryParams(state, { defaultPageSize }) {
  const preserved = { ...(state.preservedParams || {}) };
  const tag = String(preserved.tag || "").trim();
  delete preserved.tag;
  const params = {};
  if (state.view === "authors") {
    params.view = "authors";
  } else if (state.view === "author" && state.authorId) {
    params.view = "author";
    params.author = state.authorId;
  } else if (state.view === "series" && state.seriesId) {
    params.view = "series";
    params.series = state.seriesId;
  } else if (state.view === "series") {
    params.view = "series";
  } else {
    params.view = "books";
  }

  if (tag) params.tag = tag;
  if (state.q) params.q = state.q;
  Object.assign(params, preserved);
  if (state.page && state.page !== 1) params.page = state.page;
  if (state.pageSize && state.pageSize !== defaultPageSize) {
    params.page_size = state.pageSize;
  }
  return params;
}

export function bookDetailContextFromSearch(search) {
  const params = new URLSearchParams(search || "");
  const view = (params.get("view") || "").trim().toLowerCase();
  if (view === "author") {
    const id = (params.get("author") || "").trim();
    return id ? { kind: "author", id, name: "Author" } : null;
  }
  if (view === "series") {
    const id = (params.get("series") || "").trim();
    return id ? { kind: "series", id, name: "Series" } : null;
  }
  return null;
}
import { productUiPath } from "../ui/paths.js";
