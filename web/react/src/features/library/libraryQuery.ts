import type { BookOrdering, LibraryAxisOrdering, LibraryAxisQuery, LibraryBooksQuery } from "@second-pass/spl-api";

export type LibraryView = "books" | "authors" | "series";
export type LibraryBookUiOrdering = Extract<BookOrdering,
  "title" | "-title" | "author" | "-author" | "series" | "-series">;
export type LibraryUiOrdering = LibraryBookUiOrdering | LibraryAxisOrdering;

export interface LibraryUrlState {
  view: LibraryView;
  tag?: string;
  ordering: LibraryUiOrdering;
  page: number;
  pageSize: number;
  q: string;
}

export interface LibraryOrderingOption {
  value: LibraryUiOrdering;
  label: string;
  icon: string;
}

export const libraryBookOrderingOptions: readonly LibraryOrderingOption[] = [
  { value: "title", label: "Title A-Z", icon: "sort_by_alpha" },
  { value: "-title", label: "Title Z-A", icon: "sort_by_alpha" },
  { value: "author", label: "Author A-Z", icon: "person" },
  { value: "-author", label: "Author Z-A", icon: "person" },
  { value: "series", label: "Series A-Z", icon: "auto_stories" },
  { value: "-series", label: "Series Z-A", icon: "auto_stories" },
];

export const libraryAxisOrderingOptions: readonly LibraryOrderingOption[] = [
  { value: "name", label: "Name A-Z", icon: "sort_by_alpha" },
  { value: "-name", label: "Name Z-A", icon: "sort_by_alpha" },
  { value: "-book_count", label: "Most Books", icon: "library_books" },
  { value: "book_count", label: "Fewest Books", icon: "library_books" },
];

const views = new Set<LibraryView>(["books", "authors", "series"]);
const bookOrderings = new Set(libraryBookOrderingOptions.map(({ value }) => value));
const axisOrderings = new Set(libraryAxisOrderingOptions.map(({ value }) => value));
const pageSizes = new Set([20, 30, 40, 50]);

export function libraryStateFromSearchParams(parameters: URLSearchParams): LibraryUrlState {
  const rawView = parameters.get("view") as LibraryView | null;
  const view = rawView && views.has(rawView) ? rawView : "books";
  const rawOrdering = parameters.get("ordering") as LibraryUiOrdering | null;
  const allowedOrderings = view === "books" ? bookOrderings : axisOrderings;
  const defaultOrdering = libraryDefaultOrdering(view);
  const rawPageSize = positiveInteger(parameters.get("page_size"), 20);
  const tag = (parameters.get("tag") ?? "").trim();
  return {
    view,
    ...(tag ? { tag } : {}),
    ordering: rawOrdering && allowedOrderings.has(rawOrdering) ? rawOrdering : defaultOrdering,
    page: positiveInteger(parameters.get("page"), 1),
    pageSize: pageSizes.has(rawPageSize) ? rawPageSize : 20,
    q: (parameters.get("q") ?? "").trim(),
  };
}

export function librarySearchParams(state: LibraryUrlState): URLSearchParams {
  const parameters = new URLSearchParams();
  if (state.view !== "books") parameters.set("view", state.view);
  if (state.tag) parameters.set("tag", state.tag);
  if (state.ordering !== libraryDefaultOrdering(state.view)) parameters.set("ordering", state.ordering);
  if (state.page > 1) parameters.set("page", String(state.page));
  if (state.pageSize !== 20) parameters.set("page_size", String(state.pageSize));
  if (state.q) parameters.set("q", state.q);
  return parameters;
}

export function libraryPath(state: LibraryUrlState): string {
  const query = librarySearchParams(state).toString();
  return `/library${query ? `?${query}` : ""}`;
}

export function withLibraryChange(
  current: LibraryUrlState,
  changes: Partial<Omit<LibraryUrlState, "view">>,
  resetPage = true,
): LibraryUrlState {
  return { ...current, ...changes, page: resetPage ? 1 : changes.page ?? current.page };
}

export function withLibraryView(current: LibraryUrlState, view: LibraryView): LibraryUrlState {
  return {
    view,
    ...(current.tag ? { tag: current.tag } : {}),
    ordering: libraryDefaultOrdering(view),
    page: 1,
    pageSize: current.pageSize,
    q: "",
  };
}

export function libraryDefaultOrdering(view: LibraryView): LibraryUiOrdering {
  return view === "books" ? "title" : "name";
}

export function libraryOrderingOptions(view: LibraryView): readonly LibraryOrderingOption[] {
  return view === "books" ? libraryBookOrderingOptions : libraryAxisOrderingOptions;
}

export function libraryBooksSdkQuery(state: LibraryUrlState): LibraryBooksQuery {
  return {
    ...(state.q ? { q: state.q } : {}),
    ...(state.tag ? { tag: state.tag } : {}),
    ordering: state.ordering as LibraryBookUiOrdering,
    page: state.page,
    pageSize: state.pageSize,
  };
}

export function libraryAxisSdkQuery(state: LibraryUrlState): LibraryAxisQuery {
  return {
    ...(state.q ? { q: state.q } : {}),
    ...(state.tag ? { tag: state.tag } : {}),
    ordering: state.ordering as LibraryAxisOrdering,
    includePreviewBooks: true,
    page: state.page,
    pageSize: state.pageSize,
  };
}

function positiveInteger(raw: string | null, fallback: number): number {
  const value = Number(raw);
  return Number.isInteger(value) && value > 0 ? value : fallback;
}
