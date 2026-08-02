import type { MarginaliaSessionsQuery } from "@second-pass/spl-api";

export type MarginaliaExportStatusFilter = "all" | "active" | "closed";

export interface MarginaliaExportUrlState {
  q: string;
  status: MarginaliaExportStatusFilter;
  page: number;
  pageSize: number;
}

const pageSizes = new Set([20, 30, 40, 50]);
const statuses = new Set<MarginaliaExportStatusFilter>(["all", "active", "closed"]);

export function marginaliaExportStateFromSearchParams(parameters: URLSearchParams): MarginaliaExportUrlState {
  const rawStatus = parameters.get("status") as MarginaliaExportStatusFilter | null;
  return {
    q: (parameters.get("q") ?? "").trim(),
    status: rawStatus && statuses.has(rawStatus) ? rawStatus : "all",
    page: positiveInteger(parameters.get("page"), 1),
    pageSize: validPageSize(parameters.get("page_size")),
  };
}

export function marginaliaExportSearchParams(state: MarginaliaExportUrlState): URLSearchParams {
  const parameters = new URLSearchParams();
  if (state.status !== "all") parameters.set("status", state.status);
  if (state.page > 1) parameters.set("page", String(state.page));
  if (state.pageSize !== 20) parameters.set("page_size", String(state.pageSize));
  if (state.q) parameters.set("q", state.q);
  return parameters;
}

export function marginaliaExportSdkQuery(state: MarginaliaExportUrlState): MarginaliaSessionsQuery {
  return {
    ...(state.q ? { q: state.q } : {}),
    ...(state.status !== "all" ? { status: state.status } : {}),
    page: state.page,
    pageSize: state.pageSize,
  };
}

export function marginaliaExportCandidateQuery(
  state: MarginaliaExportUrlState,
  includeEmptySessions: boolean,
): MarginaliaSessionsQuery {
  return {
    ...marginaliaExportSdkQuery(state),
    ...(includeEmptySessions ? {} : { hasAnnotations: true }),
  };
}

export function withMarginaliaExportChange(
  current: MarginaliaExportUrlState,
  changes: Partial<MarginaliaExportUrlState>,
  resetPage = true,
): MarginaliaExportUrlState {
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
