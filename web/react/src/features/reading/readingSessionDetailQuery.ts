import type { ReadingAnnotationCategory, ReadingAnnotationOrdering, ReadingAnnotationsQuery } from "@second-pass/spl-api";

export type ReadingAnnotationOrder = "newest" | "oldest" | "recently-edited" | "oldest-edited";

export interface ReadingSessionDetailUrlState {
  categories: ReadingAnnotationCategory[];
  order: ReadingAnnotationOrder;
  page: number;
  pageSize: number;
}

export const allReadingAnnotationCategories: readonly ReadingAnnotationCategory[] = ["bookmark", "highlight", "highlightWithNote"];
export const defaultReadingAnnotationCategories: readonly ReadingAnnotationCategory[] = ["highlight", "highlightWithNote"];
const categoryQueryValues: Record<ReadingAnnotationCategory, string> = {
  bookmark: "bookmark",
  highlight: "highlight",
  highlightWithNote: "highlight-with-note",
};
const categoriesByQueryValue = new Map(Object.entries(categoryQueryValues).map(([category, value]) => [value, category as ReadingAnnotationCategory]));
const orders: readonly ReadingAnnotationOrder[] = ["newest", "oldest", "recently-edited", "oldest-edited"];
const pageSizes = [20, 30, 40, 50] as const;

export function readingSessionDetailStateFromSearchParams(parameters: URLSearchParams): ReadingSessionDetailUrlState {
  const requestedCategories = parameters.getAll("show");
  const parsedCategories = requestedCategories.map((value) => categoriesByQueryValue.get(value));
  const categories = requestedCategories.length > 0 && parsedCategories.every((category) => category !== undefined)
    ? allReadingAnnotationCategories.filter((category) => parsedCategories.includes(category))
    : [...defaultReadingAnnotationCategories];
  const order = parameters.get("order");
  const page = positiveInteger(parameters.get("page"), 1);
  const pageSize = positiveInteger(parameters.get("page_size"), 20);
  return {
    categories,
    order: orders.includes(order as ReadingAnnotationOrder) ? order as ReadingAnnotationOrder : "newest",
    page,
    pageSize: pageSizes.includes(pageSize as (typeof pageSizes)[number]) ? pageSize : 20,
  };
}

export function readingSessionDetailSearchParams(state: ReadingSessionDetailUrlState): URLSearchParams {
  const parameters = new URLSearchParams();
  if (!sameCategories(state.categories, defaultReadingAnnotationCategories)) {
    for (const category of allReadingAnnotationCategories) {
      if (state.categories.includes(category)) parameters.append("show", categoryQueryValues[category]);
    }
  }
  if (state.order !== "newest") parameters.set("order", state.order);
  if (state.page !== 1) parameters.set("page", String(state.page));
  if (state.pageSize !== 20) parameters.set("page_size", String(state.pageSize));
  return parameters;
}

export function withReadingSessionDetailChange(state: ReadingSessionDetailUrlState, changes: Partial<ReadingSessionDetailUrlState>, resetPage = true): ReadingSessionDetailUrlState {
  return { ...state, ...changes, page: resetPage && changes.page === undefined ? 1 : changes.page ?? state.page };
}

export function readingAnnotationsSdkQuery(sessionId: string, state: ReadingSessionDetailUrlState): ReadingAnnotationsQuery {
  const orderingByUiValue: Record<ReadingAnnotationOrder, ReadingAnnotationOrdering> = {
    newest: "-created",
    oldest: "created",
    "recently-edited": "-modified",
    "oldest-edited": "modified",
  };
  return {
    sessionId,
    ...(state.categories.length === allReadingAnnotationCategories.length ? {} : { categories: state.categories }),
    ordering: orderingByUiValue[state.order],
    page: state.page,
    pageSize: state.pageSize,
  };
}

function positiveInteger(value: string | null, fallback: number): number {
  if (!value || !/^\d+$/.test(value)) return fallback;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : fallback;
}

function sameCategories(left: readonly ReadingAnnotationCategory[], right: readonly ReadingAnnotationCategory[]): boolean {
  return left.length === right.length && right.every((category) => left.includes(category));
}
