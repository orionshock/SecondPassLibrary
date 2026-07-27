import type {
  BookOrdering,
  GroupBooksQuery,
  GroupMembersQuery,
  LibraryGroupsQuery,
  ShelvesQuery,
} from "@second-pass/spl-api";

import { resolveTabQuery, withTabQuery } from "../../app/routing/tabQuery";

export type GroupBookOrdering = Extract<BookOrdering,
  "title" | "-title" | "author" | "-author" | "series" | "-series">;
export type GroupDetailTab = "books" | "members" | "shelves";
export type GroupEditTab = "details" | "books" | "add-books" | "members";

export interface GroupsListUrlState {
  q: string;
  ordering: "name" | "-name";
  page: number;
  pageSize: number;
}

export interface GroupDetailUrlState {
  tab: GroupDetailTab;
  q: string;
  ordering: GroupBookOrdering;
  page: number;
  pageSize: number;
}

export interface GroupEditQueryState {
  tab: GroupEditTab;
  query: string;
}

const pageSizes = new Set([20, 30, 40, 50]);
const groupOrderings = new Set(["name", "-name"] as const);
const bookOrderings = new Set<GroupBookOrdering>([
  "title", "-title", "author", "-author", "series", "-series",
]);
const groupDetailTabs: readonly GroupDetailTab[] = ["books", "members", "shelves"];
const groupEditTabs: readonly GroupEditTab[] = ["details", "books", "add-books", "members"];

export function groupsListStateFromSearchParams(parameters: URLSearchParams): GroupsListUrlState {
  const rawOrdering = parameters.get("ordering") as GroupsListUrlState["ordering"] | null;
  return {
    q: (parameters.get("q") ?? "").trim(),
    ordering: rawOrdering && groupOrderings.has(rawOrdering) ? rawOrdering : "name",
    page: positiveInteger(parameters.get("page"), 1),
    pageSize: validPageSize(parameters.get("page_size")),
  };
}

export function groupsListSearchParams(state: GroupsListUrlState): URLSearchParams {
  const parameters = new URLSearchParams();
  if (state.ordering !== "name") parameters.set("ordering", state.ordering);
  if (state.page > 1) parameters.set("page", String(state.page));
  if (state.pageSize !== 20) parameters.set("page_size", String(state.pageSize));
  if (state.q) parameters.set("q", state.q);
  return parameters;
}

export function groupsListPath(state: GroupsListUrlState): string {
  return withQuery("/groups", groupsListSearchParams(state));
}

export function groupsListSdkQuery(state: GroupsListUrlState): LibraryGroupsQuery {
  return {
    ...(state.q ? { q: state.q } : {}),
    ordering: state.ordering,
    includePreviewBooks: true,
    page: state.page,
    pageSize: state.pageSize,
  };
}

export function withGroupsListChange(
  current: GroupsListUrlState,
  changes: Partial<GroupsListUrlState>,
  resetPage = true,
): GroupsListUrlState {
  return { ...current, ...changes, page: resetPage ? 1 : changes.page ?? current.page };
}

export function groupDetailStateFromSearchParams(parameters: URLSearchParams): GroupDetailUrlState {
  const { tab } = resolveTabQuery(parameters, groupDetailTabs, "books");
  const rawOrdering = parameters.get("ordering") as GroupBookOrdering | null;
  return {
    tab,
    q: tab === "books" ? (parameters.get("q") ?? "").trim() : "",
    ordering: tab === "books" && rawOrdering && bookOrderings.has(rawOrdering)
      ? rawOrdering
      : "title",
    page: positiveInteger(parameters.get("page"), 1),
    pageSize: validPageSize(parameters.get("page_size")),
  };
}

export function groupDetailSearchParams(state: GroupDetailUrlState): URLSearchParams {
  const parameters = withTabQuery(new URLSearchParams(), state.tab, "books");
  if (state.tab === "books" && state.ordering !== "title") parameters.set("ordering", state.ordering);
  if (state.page > 1) parameters.set("page", String(state.page));
  if (state.pageSize !== 20) parameters.set("page_size", String(state.pageSize));
  if (state.tab === "books" && state.q) parameters.set("q", state.q);
  return parameters;
}

export function groupDetailPath(groupId: string, state: GroupDetailUrlState): string {
  return withQuery(`/groups/${encodeURIComponent(groupId)}`, groupDetailSearchParams(state));
}

export function withGroupDetailChange(
  current: GroupDetailUrlState,
  changes: Partial<GroupDetailUrlState>,
  resetPage = true,
): GroupDetailUrlState {
  const next = { ...current, ...changes, page: resetPage ? 1 : changes.page ?? current.page };
  return next.tab !== "books" ? { ...next, q: "", ordering: "title" } : next;
}

export function groupBooksSdkQuery(state: GroupDetailUrlState): GroupBooksQuery {
  return {
    ...(state.q ? { q: state.q } : {}),
    ordering: state.ordering,
    page: state.page,
    pageSize: state.pageSize,
  };
}

export function groupMembersSdkQuery(state: GroupDetailUrlState): GroupMembersQuery {
  return { page: state.page, pageSize: state.pageSize };
}

export function groupShelvesSdkQuery(groupId: string, state: GroupDetailUrlState): ShelvesQuery {
  return {
    scope: "group",
    ownerGroupId: groupId,
    ordering: "name",
    includePreviewBooks: true,
    page: state.page,
    pageSize: state.pageSize,
  };
}

export function groupEditQueryFromSearchParams(parameters: URLSearchParams): GroupEditQueryState {
  const { tab } = resolveTabQuery(parameters, groupEditTabs, "details");
  return {
    tab,
    query: withTabQuery(parameters, tab, "details").toString(),
  };
}

export function groupEditSearchParams(
  parameters: URLSearchParams,
  tab: GroupEditTab,
): URLSearchParams {
  return withTabQuery(parameters, tab, "details");
}

export function groupEditQueryDuringImmediateMutation(
  requested: GroupEditQueryState,
  stable: GroupEditQueryState,
  pending: boolean,
): GroupEditQueryState {
  return pending ? stable : requested;
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
