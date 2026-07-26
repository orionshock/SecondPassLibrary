import type {
  ShelfItemOrdering,
  ShelfItemsQuery,
  ShelfOrdering,
  ShelfScope,
  ShelvesQuery,
} from "@second-pass/spl-api";

export interface ShelvesListUrlState {
  scope: ShelfScope;
  ordering: ShelfOrdering;
  page: number;
  pageSize: number;
}

export interface ShelfDetailUrlState {
  ordering: ShelfItemOrdering;
  page: number;
  pageSize: number;
}

const pageSizes = new Set([20, 30, 40, 50]);
const scopes = new Set<ShelfScope>(["personal", "shared", "group"]);
const shelfOrderings = new Set<ShelfOrdering>(["name", "-item_count"]);
const itemOrderings = new Set<ShelfItemOrdering>(["position", "title", "author"]);

export function shelvesListStateFromSearchParams(parameters: URLSearchParams): ShelvesListUrlState {
  const rawScope = parameters.get("scope") as ShelfScope | null;
  const rawOrdering = parameters.get("ordering") as ShelfOrdering | null;
  return {
    scope: rawScope && scopes.has(rawScope) ? rawScope : "personal",
    ordering: rawOrdering && shelfOrderings.has(rawOrdering) ? rawOrdering : "name",
    page: positiveInteger(parameters.get("page"), 1),
    pageSize: validPageSize(parameters.get("page_size")),
  };
}

export function shelvesListSearchParams(state: ShelvesListUrlState): URLSearchParams {
  const parameters = new URLSearchParams();
  if (state.scope !== "personal") parameters.set("scope", state.scope);
  if (state.ordering !== "name") parameters.set("ordering", state.ordering);
  if (state.page > 1) parameters.set("page", String(state.page));
  if (state.pageSize !== 20) parameters.set("page_size", String(state.pageSize));
  return parameters;
}

export function shelvesListPath(state: ShelvesListUrlState): string {
  return withQuery("/shelves", shelvesListSearchParams(state));
}

export function shelvesListSdkQuery(state: ShelvesListUrlState): ShelvesQuery {
  return {
    scope: state.scope,
    ordering: state.ordering,
    includePreviewBooks: true,
    page: state.page,
    pageSize: state.pageSize,
  };
}

export function withShelvesListChange(
  current: ShelvesListUrlState,
  changes: Partial<ShelvesListUrlState>,
  resetPage = true,
): ShelvesListUrlState {
  return { ...current, ...changes, page: resetPage ? 1 : changes.page ?? current.page };
}

export function shelfDetailStateFromSearchParams(parameters: URLSearchParams): ShelfDetailUrlState {
  const rawOrdering = parameters.get("ordering") as ShelfItemOrdering | null;
  return {
    ordering: rawOrdering && itemOrderings.has(rawOrdering) ? rawOrdering : "position",
    page: positiveInteger(parameters.get("page"), 1),
    pageSize: validPageSize(parameters.get("page_size")),
  };
}

export function shelfDetailSearchParams(state: ShelfDetailUrlState): URLSearchParams {
  const parameters = new URLSearchParams();
  if (state.ordering !== "position") parameters.set("ordering", state.ordering);
  if (state.page > 1) parameters.set("page", String(state.page));
  if (state.pageSize !== 20) parameters.set("page_size", String(state.pageSize));
  return parameters;
}

export function shelfDetailPath(shelfId: string, state: ShelfDetailUrlState): string {
  return withQuery(`/shelves/${encodeURIComponent(shelfId)}`, shelfDetailSearchParams(state));
}

export function shelfItemsSdkQuery(state: ShelfDetailUrlState): ShelfItemsQuery {
  return { ordering: state.ordering, page: state.page, pageSize: state.pageSize };
}

export function withShelfDetailChange(
  current: ShelfDetailUrlState,
  changes: Partial<ShelfDetailUrlState>,
  resetPage = true,
): ShelfDetailUrlState {
  return { ...current, ...changes, page: resetPage ? 1 : changes.page ?? current.page };
}

function validPageSize(raw: string | null): number {
  const value = positiveInteger(raw, 20);
  return pageSizes.has(value) ? value : 20;
}

function positiveInteger(raw: string | null, fallback: number): number {
  const value = Number(raw);
  return Number.isInteger(value) && value > 0 ? value : fallback;
}

function withQuery(path: string, parameters: URLSearchParams): string {
  const query = parameters.toString();
  return `${path}${query ? `?${query}` : ""}`;
}
