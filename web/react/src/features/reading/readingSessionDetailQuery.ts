import type { ReadingAnnotationKind, ReadingAnnotationOrdering, ReadingAnnotationsQuery } from "@second-pass/spl-api";

export type ReadingAnnotationFilter = "all" | ReadingAnnotationKind;
export type ReadingAnnotationOrder = "newest" | "oldest";

export interface ReadingSessionDetailUrlState {
  filter: ReadingAnnotationFilter;
  order: ReadingAnnotationOrder;
  page: number;
  pageSize: number;
}

const filters: readonly ReadingAnnotationFilter[] = ["all", "highlight", "bookmark"];
const orders: readonly ReadingAnnotationOrder[] = ["newest", "oldest"];
const pageSizes = [20, 30, 40, 50] as const;

export function readingSessionDetailStateFromSearchParams(parameters: URLSearchParams): ReadingSessionDetailUrlState {
  const filter = parameters.get("kind");
  const order = parameters.get("order");
  const page = positiveInteger(parameters.get("page"), 1);
  const pageSize = positiveInteger(parameters.get("page_size"), 20);
  return {
    filter: filters.includes(filter as ReadingAnnotationFilter) ? filter as ReadingAnnotationFilter : "all",
    order: orders.includes(order as ReadingAnnotationOrder) ? order as ReadingAnnotationOrder : "newest",
    page,
    pageSize: pageSizes.includes(pageSize as (typeof pageSizes)[number]) ? pageSize : 20,
  };
}

export function readingSessionDetailSearchParams(state: ReadingSessionDetailUrlState): URLSearchParams {
  const parameters = new URLSearchParams();
  if (state.filter !== "all") parameters.set("kind", state.filter);
  if (state.order !== "newest") parameters.set("order", state.order);
  if (state.page !== 1) parameters.set("page", String(state.page));
  if (state.pageSize !== 20) parameters.set("page_size", String(state.pageSize));
  return parameters;
}

export function withReadingSessionDetailChange(state: ReadingSessionDetailUrlState, changes: Partial<ReadingSessionDetailUrlState>, resetPage = true): ReadingSessionDetailUrlState {
  return { ...state, ...changes, page: resetPage && changes.page === undefined ? 1 : changes.page ?? state.page };
}

export function readingAnnotationsSdkQuery(sessionId: string, state: ReadingSessionDetailUrlState): ReadingAnnotationsQuery {
  return {
    sessionId,
    ...(state.filter === "all" ? {} : { kind: state.filter }),
    ordering: (state.order === "newest" ? "-created" : "created") satisfies ReadingAnnotationOrdering,
    page: state.page,
    pageSize: state.pageSize,
  };
}

function positiveInteger(value: string | null, fallback: number): number {
  if (!value || !/^\d+$/.test(value)) return fallback;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : fallback;
}
