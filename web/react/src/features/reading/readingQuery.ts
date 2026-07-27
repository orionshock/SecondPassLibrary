import type { ReadingSessionsQuery } from "@second-pass/spl-api";

export type ReadingStatusFilter = "all" | "active" | "historical";

export interface ReadingListUrlState {
  q: string;
  status: ReadingStatusFilter;
  page: number;
  pageSize: number;
}

const pageSizes = new Set([20, 30, 40, 50]);
const statuses = new Set<ReadingStatusFilter>(["all", "active", "historical"]);

export function readingListStateFromSearchParams(parameters: URLSearchParams): ReadingListUrlState {
  const rawStatus = parameters.get("status") as ReadingStatusFilter | null;
  return {
    q: (parameters.get("q") ?? "").trim(),
    status: rawStatus && statuses.has(rawStatus) ? rawStatus : "all",
    page: positiveInteger(parameters.get("page"), 1),
    pageSize: validPageSize(parameters.get("page_size")),
  };
}

export function readingListSearchParams(state: ReadingListUrlState): URLSearchParams {
  const parameters = new URLSearchParams();
  if (state.status !== "all") parameters.set("status", state.status);
  if (state.page > 1) parameters.set("page", String(state.page));
  if (state.pageSize !== 20) parameters.set("page_size", String(state.pageSize));
  if (state.q) parameters.set("q", state.q);
  return parameters;
}

export function readingListSdkQuery(state: ReadingListUrlState): ReadingSessionsQuery {
  return {
    ...(state.q ? { q: state.q } : {}),
    ...(state.status === "active" ? { isActive: true } : {}),
    ...(state.status === "historical" ? { isActive: false } : {}),
    page: state.page,
    pageSize: state.pageSize,
  };
}

export function withReadingListChange(
  current: ReadingListUrlState,
  changes: Partial<ReadingListUrlState>,
  resetPage = true,
): ReadingListUrlState {
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
