import type { UserOrdering, UserRoleFilter, UsersListQuery, UserStatusFilter } from "@second-pass/spl-api";

export interface UsersListUrlState {
  q: string;
  role?: UserRoleFilter;
  isActive?: UserStatusFilter;
  ordering: UserOrdering;
  page: number;
  pageSize: number;
}

export const userRoleFilters: ReadonlyArray<{ value?: UserRoleFilter; label: string }> = [
  { label: "All" },
  { value: "reader", label: "Reader" },
  { value: "curator", label: "Curator" },
  { value: "librarian", label: "Librarian" },
  { value: "manager", label: "Manager" },
  { value: "owner", label: "Owner" },
];

const orderings = new Set<UserOrdering>([
  "username", "-username", "name", "-name", "role", "-role", "is_active", "-is_active",
]);
const roles = new Set<UserRoleFilter>(["owner", "manager", "librarian", "reader", "curator"]);
const pageSizes = new Set([20, 50, 100, 200]);

export function usersListStateFromSearchParams(parameters: URLSearchParams, advancedGroupsEnabled: boolean): UsersListUrlState {
  const rawRole = parameters.get("role") as UserRoleFilter | null;
  const role = rawRole && roles.has(rawRole) && (rawRole !== "curator" || advancedGroupsEnabled) ? rawRole : undefined;
  const rawStatus = parameters.get("is_active");
  const isActive = rawStatus === "true" || rawStatus === "false" ? rawStatus : undefined;
  const rawOrdering = parameters.get("ordering") as UserOrdering | null;
  const ordering = rawOrdering && orderings.has(rawOrdering) ? rawOrdering : "username";
  const page = positiveInteger(parameters.get("page"), 1);
  const requestedPageSize = positiveInteger(parameters.get("page_size"), 50);

  return {
    q: (parameters.get("q") ?? "").trim(),
    role,
    isActive,
    ordering,
    page,
    pageSize: pageSizes.has(requestedPageSize) ? requestedPageSize : 50,
  };
}

export function withUsersListChange(
  current: UsersListUrlState,
  changes: Partial<UsersListUrlState>,
  resetPage = true,
): UsersListUrlState {
  return { ...current, ...changes, page: resetPage ? 1 : changes.page ?? current.page };
}

export function usersListSearchParams(state: UsersListUrlState): URLSearchParams {
  const parameters = new URLSearchParams();
  if (state.q) parameters.set("q", state.q);
  if (state.role) parameters.set("role", state.role);
  if (state.isActive) parameters.set("is_active", state.isActive);
  if (state.ordering !== "username") parameters.set("ordering", state.ordering);
  if (state.page > 1) parameters.set("page", String(state.page));
  if (state.pageSize !== 50) parameters.set("page_size", String(state.pageSize));
  return parameters;
}

export function usersListSdkQuery(state: UsersListUrlState): UsersListQuery {
  return {
    ...(state.q ? { q: state.q } : {}),
    ...(state.role ? { role: state.role } : {}),
    ...(state.isActive ? { isActive: state.isActive } : {}),
    ordering: state.ordering,
    page: state.page,
    pageSize: state.pageSize,
  };
}

export function nextUserOrdering(current: UserOrdering, key: "username" | "name" | "role" | "is_active"): UserOrdering {
  return current === key ? `-${key}` : key;
}

function positiveInteger(raw: string | null, fallback: number): number {
  const value = Number(raw);
  return Number.isInteger(value) && value > 0 ? value : fallback;
}
