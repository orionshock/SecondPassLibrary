import type { ReadingAnnotationCategory, ReadingAnnotationOrdering, ReadingAnnotationsQuery } from "@second-pass/spl-api";

export type MarginaliaAnnotationOrder = "newest" | "oldest" | "recently-edited" | "oldest-edited";

export interface MarginaliaSessionDetailUrlState {
  categories: ReadingAnnotationCategory[];
  order: MarginaliaAnnotationOrder;
  page: number;
  pageSize: number;
}

export const allMarginaliaAnnotationCategories: readonly ReadingAnnotationCategory[] = ["bookmark", "highlight", "highlightWithNote"];
export const defaultMarginaliaAnnotationCategories: readonly ReadingAnnotationCategory[] = ["highlight", "highlightWithNote"];
const categoryQueryValues: Record<ReadingAnnotationCategory, string> = {
  bookmark: "bookmark",
  highlight: "highlight",
  highlightWithNote: "highlight-with-note",
};
const categoriesByQueryValue = new Map(Object.entries(categoryQueryValues).map(([category, value]) => [value, category as ReadingAnnotationCategory]));
const orders: readonly MarginaliaAnnotationOrder[] = ["newest", "oldest", "recently-edited", "oldest-edited"];
const pageSizes = [20, 30, 40, 50] as const;

export function marginaliaSessionDetailStateFromSearchParams(parameters: URLSearchParams): MarginaliaSessionDetailUrlState {
  const requestedCategories = parameters.getAll("show");
  const parsedCategories = requestedCategories.map((value) => categoriesByQueryValue.get(value));
  const categories = requestedCategories.length > 0 && parsedCategories.every((category) => category !== undefined)
    ? allMarginaliaAnnotationCategories.filter((category) => parsedCategories.includes(category))
    : [...defaultMarginaliaAnnotationCategories];
  const order = parameters.get("order");
  const page = positiveInteger(parameters.get("page"), 1);
  const pageSize = positiveInteger(parameters.get("page_size"), 20);
  return {
    categories,
    order: orders.includes(order as MarginaliaAnnotationOrder) ? order as MarginaliaAnnotationOrder : "newest",
    page,
    pageSize: pageSizes.includes(pageSize as (typeof pageSizes)[number]) ? pageSize : 20,
  };
}

export function marginaliaSessionDetailSearchParams(state: MarginaliaSessionDetailUrlState): URLSearchParams {
  const parameters = new URLSearchParams();
  if (!sameCategories(state.categories, defaultMarginaliaAnnotationCategories)) {
    for (const category of allMarginaliaAnnotationCategories) {
      if (state.categories.includes(category)) parameters.append("show", categoryQueryValues[category]);
    }
  }
  if (state.order !== "newest") parameters.set("order", state.order);
  if (state.page !== 1) parameters.set("page", String(state.page));
  if (state.pageSize !== 20) parameters.set("page_size", String(state.pageSize));
  return parameters;
}

export function withMarginaliaSessionDetailChange(state: MarginaliaSessionDetailUrlState, changes: Partial<MarginaliaSessionDetailUrlState>, resetPage = true): MarginaliaSessionDetailUrlState {
  return { ...state, ...changes, page: resetPage && changes.page === undefined ? 1 : changes.page ?? state.page };
}

export function marginaliaAnnotationsSdkQuery(sessionId: string, state: MarginaliaSessionDetailUrlState): ReadingAnnotationsQuery {
  const orderingByUiValue: Record<MarginaliaAnnotationOrder, ReadingAnnotationOrdering> = {
    newest: "-created",
    oldest: "created",
    "recently-edited": "-modified",
    "oldest-edited": "modified",
  };
  return {
    sessionId,
    ...(state.categories.length === allMarginaliaAnnotationCategories.length ? {} : { categories: state.categories }),
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
