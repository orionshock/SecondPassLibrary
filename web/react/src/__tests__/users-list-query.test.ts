import { describe, expect, it } from "vitest";

import {
  nextUserOrdering,
  userRoleFilters,
  usersListSdkQuery,
  usersListSearchParams,
  usersListStateFromSearchParams,
  withUsersListChange,
} from "../features/users/usersListQuery";

describe("Users list URL state", () => {
  it("uses page size 20 for an unparameterized Users request without adding it to the URL", () => {
    const state = usersListStateFromSearchParams(new URLSearchParams(), true);
    expect(usersListSdkQuery(state).pageSize).toBe(20);
    expect(usersListSearchParams(state).has("page_size")).toBe(false);
  });

  it("reads URL-backed filters, ordering, page, and page size for the SDK", () => {
    const state = usersListStateFromSearchParams(new URLSearchParams("q=ada&role=manager&is_active=false&ordering=-name&page=3&page_size=20"), true);
    expect(usersListSdkQuery(state)).toEqual({ q: "ada", role: "manager", isActive: "false", ordering: "-name", page: 3, pageSize: 20 });
    expect(usersListSearchParams(state).toString()).toBe("q=ada&role=manager&is_active=false&ordering=-name&page=3&page_size=20");
  });

  it("resets page for query changes but preserves an explicitly selected page", () => {
    const current = usersListStateFromSearchParams(new URLSearchParams("page=4&page_size=20"), true);
    expect(withUsersListChange(current, { q: "reader" }).page).toBe(1);
    expect(withUsersListChange(current, { role: "owner" }).page).toBe(1);
    expect(withUsersListChange(current, { isActive: "true" }).page).toBe(1);
    expect(withUsersListChange(current, { ordering: "role" }).page).toBe(1);
    const changedPageSize = withUsersListChange(current, { pageSize: 100 });
    expect(changedPageSize.page).toBe(1);
    expect(usersListSearchParams(changedPageSize).get("page_size")).toBe("100");
    expect(usersListSdkQuery(changedPageSize).pageSize).toBe(100);
    expect(withUsersListChange(current, { page: 2 }, false).page).toBe(2);
  });

  it("restores independent URL states and removes unavailable Curator filtering in simple mode", () => {
    expect(usersListStateFromSearchParams(new URLSearchParams("q=first&page=2"), true).q).toBe("first");
    expect(usersListStateFromSearchParams(new URLSearchParams("q=second&page=5"), true).page).toBe(5);
    expect(usersListStateFromSearchParams(new URLSearchParams("role=curator"), false).role).toBeUndefined();
    expect(usersListStateFromSearchParams(new URLSearchParams("role=curator"), true).role).toBe("curator");
    expect(usersListStateFromSearchParams(new URLSearchParams("page_size=invalid"), true).pageSize).toBe(20);
    expect(usersListStateFromSearchParams(new URLSearchParams("page_size=21"), true).pageSize).toBe(20);
  });

  it("keeps the required role order and toggles server ordering direction", () => {
    expect(userRoleFilters.map(({ label }) => label)).toEqual(["All", "Reader", "Curator", "Librarian", "Manager", "Owner"]);
    expect(nextUserOrdering("username", "username")).toBe("-username");
    expect(nextUserOrdering("-username", "username")).toBe("username");
    expect(nextUserOrdering("name", "role")).toBe("role");
  });
});
