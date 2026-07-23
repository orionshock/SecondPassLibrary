import type { BookOrdering, LibraryBooksQuery } from "@second-pass/spl-api";

export interface LibraryUrlState {
  view: "books";
  tag?: string;
  ordering: LibraryBookUiOrdering;
  page: number;
  pageSize: number;
  q: string;
}

export type LibraryBookUiOrdering = Extract<BookOrdering,
  "title" | "-title" | "author" | "-author" | "series" | "-series">;

export const libraryOrderingOptions: ReadonlyArray<{ value: LibraryBookUiOrdering; label: string }> = [
  { value: "title", label: "Title (A-Z)" },
  { value: "-title", label: "Title (Z-A)" },
  { value: "author", label: "Author (A-Z)" },
  { value: "-author", label: "Author (Z-A)" },
  { value: "series", label: "Series (A-Z)" },
  { value: "-series", label: "Series (Z-A)" },
];

const orderings = new Set(libraryOrderingOptions.map(({ value }) => value));
const pageSizes = new Set([20, 30, 40, 50]);

export function libraryStateFromSearchParams(parameters: URLSearchParams): LibraryUrlState {
  const rawOrdering = parameters.get("ordering") as LibraryBookUiOrdering | null;
  const rawPageSize = positiveInteger(parameters.get("page_size"), 20);
  const tag = (parameters.get("tag") ?? "").trim();
  return {
    view: "books",
    ...(tag ? { tag } : {}),
    ordering: rawOrdering && orderings.has(rawOrdering) ? rawOrdering : "title",
    page: positiveInteger(parameters.get("page"), 1),
    pageSize: pageSizes.has(rawPageSize) ? rawPageSize : 20,
    q: (parameters.get("q") ?? "").trim(),
  };
}

export function librarySearchParams(state: LibraryUrlState): URLSearchParams {
  const parameters = new URLSearchParams();
  // `view=books` is the only implemented axis and therefore canonicalizes to omission.
  if (state.tag) parameters.set("tag", state.tag);
  if (state.ordering !== "title") parameters.set("ordering", state.ordering);
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
  return {
    ...current,
    ...changes,
    page: resetPage ? 1 : changes.page ?? current.page,
  };
}

export function libraryBooksSdkQuery(state: LibraryUrlState): LibraryBooksQuery {
  return {
    ...(state.q ? { q: state.q } : {}),
    ...(state.tag ? { tag: state.tag } : {}),
    ordering: state.ordering,
    page: state.page,
    pageSize: state.pageSize,
  };
}

function positiveInteger(raw: string | null, fallback: number): number {
  const value = Number(raw);
  return Number.isInteger(value) && value > 0 ? value : fallback;
}
