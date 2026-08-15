import type { MarginaliaPageQuery, MarginaliaSessionsQuery } from "@second-pass/spl-api";

export type MarginaliaView = "sessions" | "books";
export type MarginaliaStatusFilter = "all" | "active" | "closed";
export type MarginaliaBrowseStage = "sessions" | "books" | "book-sessions";

export interface MarginaliaListUrlState {
  view: MarginaliaView;
  bookId?: string;
  q: string;
  status: MarginaliaStatusFilter;
  page: number;
  pageSize: number;
  bookSessionQ: string;
  bookSessionStatus: MarginaliaStatusFilter;
  bookSessionPage: number;
  bookSessionPageSize: number;
}

const pageSizes = new Set([20, 30, 40, 50]);
const statuses = new Set<MarginaliaStatusFilter>(["all", "active", "closed"]);

export function marginaliaListStateFromSearchParams(parameters: URLSearchParams): MarginaliaListUrlState {
  const view: MarginaliaView = parameters.get("view") === "books" ? "books" : "sessions";
  const bookId = view === "books" ? uuid(parameters.get("book")) : undefined;
  const status = view === "sessions" ? validStatus(parameters.get("status")) : "all";
  return {
    view,
    ...(bookId ? { bookId } : {}),
    q: (parameters.get("q") ?? "").trim(),
    status,
    page: positiveInteger(parameters.get("page"), 1),
    pageSize: validPageSize(parameters.get("page_size")),
    bookSessionQ: bookId ? (parameters.get("session_q") ?? "").trim() : "",
    bookSessionStatus: bookId ? validStatus(parameters.get("session_status")) : "all",
    bookSessionPage: bookId ? positiveInteger(parameters.get("session_page"), 1) : 1,
    bookSessionPageSize: bookId ? validPageSize(parameters.get("session_page_size")) : 20,
  };
}

export function marginaliaListSearchParams(state: MarginaliaListUrlState): URLSearchParams {
  const parameters = new URLSearchParams();
  if (state.view === "books") parameters.set("view", "books");
  if (state.view === "books" && state.bookId) parameters.set("book", state.bookId);
  if (state.view === "sessions" && state.status !== "all") parameters.set("status", state.status);
  if (state.page > 1) parameters.set("page", String(state.page));
  if (state.pageSize !== 20) parameters.set("page_size", String(state.pageSize));
  if (state.q) parameters.set("q", state.q);
  if (state.view === "books" && state.bookId) {
    if (state.bookSessionStatus !== "all") parameters.set("session_status", state.bookSessionStatus);
    if (state.bookSessionPage > 1) parameters.set("session_page", String(state.bookSessionPage));
    if (state.bookSessionPageSize !== 20) parameters.set("session_page_size", String(state.bookSessionPageSize));
    if (state.bookSessionQ) parameters.set("session_q", state.bookSessionQ);
  }
  return parameters;
}

export function marginaliaPath(state: MarginaliaListUrlState): string {
  const query = marginaliaListSearchParams(state).toString();
  return `/marginalia${query ? `?${query}` : ""}`;
}

export function marginaliaBrowseStage(state: MarginaliaListUrlState): MarginaliaBrowseStage {
  return state.view === "sessions" ? "sessions" : state.bookId ? "book-sessions" : "books";
}

export function marginaliaListSdkQuery(state: MarginaliaListUrlState): MarginaliaSessionsQuery {
  return {
    ...(state.q ? { q: state.q } : {}),
    ...(state.status !== "all" ? { status: state.status } : {}),
    page: state.page,
    pageSize: state.pageSize,
  };
}

export function marginaliaBooksSdkQuery(state: MarginaliaListUrlState): MarginaliaPageQuery {
  return {
    ...(state.q ? { q: state.q } : {}),
    page: state.page,
    pageSize: state.pageSize,
  };
}

export function marginaliaBookSessionsSdkQuery(state: MarginaliaListUrlState): MarginaliaSessionsQuery {
  return {
    ...(state.bookSessionQ ? { q: state.bookSessionQ } : {}),
    ...(state.bookSessionStatus !== "all" ? { status: state.bookSessionStatus } : {}),
    page: state.bookSessionPage,
    pageSize: state.bookSessionPageSize,
  };
}

export function withMarginaliaListChange(
  current: MarginaliaListUrlState,
  changes: Partial<Pick<MarginaliaListUrlState, "q" | "status" | "page" | "pageSize">>,
  resetPage = true,
): MarginaliaListUrlState {
  return { ...current, ...changes, page: resetPage ? 1 : changes.page ?? current.page };
}

export function withMarginaliaBookSessionChange(
  current: MarginaliaListUrlState,
  changes: Partial<Pick<MarginaliaListUrlState, "bookSessionQ" | "bookSessionStatus" | "bookSessionPage" | "bookSessionPageSize">>,
  resetPage = true,
): MarginaliaListUrlState {
  return { ...current, ...changes, bookSessionPage: resetPage ? 1 : changes.bookSessionPage ?? current.bookSessionPage };
}

export function withMarginaliaView(current: MarginaliaListUrlState, view: MarginaliaView): MarginaliaListUrlState {
  return {
    view,
    q: "",
    status: "all",
    page: 1,
    pageSize: current.pageSize,
    bookSessionQ: "",
    bookSessionStatus: "all",
    bookSessionPage: 1,
    bookSessionPageSize: current.bookSessionPageSize,
  };
}

export function withSelectedMarginaliaBook(current: MarginaliaListUrlState, bookId?: string): MarginaliaListUrlState {
  const { bookId: _selectedBook, ...listState } = current;
  return {
    ...listState,
    ...(bookId ? { bookId } : {}),
    bookSessionQ: "",
    bookSessionStatus: "all",
    bookSessionPage: 1,
    bookSessionPageSize: current.bookSessionPageSize,
  };
}

export function withMarginaliaSearch(current: MarginaliaListUrlState, q: string): MarginaliaListUrlState {
  return current.bookId
    ? withMarginaliaBookSessionChange(current, { bookSessionQ: q, bookSessionStatus: "all" })
    : withMarginaliaListChange(current, { q, status: "all" });
}

function validPageSize(raw: string | null): number {
  const value = positiveInteger(raw, 20);
  return pageSizes.has(value) ? value : 20;
}

function validStatus(raw: string | null): MarginaliaStatusFilter {
  return raw && statuses.has(raw as MarginaliaStatusFilter) ? raw as MarginaliaStatusFilter : "all";
}

function positiveInteger(raw: string | null, fallback: number): number {
  const value = Number(raw);
  return Number.isInteger(value) && value > 0 ? value : fallback;
}

function uuid(raw: string | null): string | undefined {
  const value = raw?.trim();
  return value && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value) ? value : undefined;
}
