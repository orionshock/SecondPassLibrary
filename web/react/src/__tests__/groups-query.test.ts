import { describe, expect, it } from "vitest";

import {
  groupBooksSdkQuery,
  groupDetailPath,
  groupDetailSearchParams,
  groupDetailStateFromSearchParams,
  groupMembersSdkQuery,
  groupShelvesSdkQuery,
  groupsListPath,
  groupsListSdkQuery,
  groupsListSearchParams,
  groupsListStateFromSearchParams,
  withGroupDetailChange,
  withGroupsListChange,
} from "../features/groups/groupsQuery";

describe("Groups URL state", () => {
  it("normalizes Group list defaults and uses canonical query order", () => {
    const defaults = groupsListStateFromSearchParams(new URLSearchParams());
    expect(groupsListPath(defaults)).toBe("/groups");
    expect(groupsListSdkQuery(defaults)).toEqual({
      ordering: "name", includePreviewBooks: true, page: 1, pageSize: 20,
    });
    const state = groupsListStateFromSearchParams(new URLSearchParams(
      "q=readers&page_size=40&page=3&ordering=-name",
    ));
    expect(groupsListSearchParams(state).toString()).toBe("ordering=-name&page=3&page_size=40&q=readers");
    expect(groupsListPath(state)).toBe("/groups?ordering=-name&page=3&page_size=40&q=readers");
    expect(groupsListStateFromSearchParams(new URLSearchParams("ordering=bad&page=0&page_size=99"))).toEqual(defaults);
  });

  it("resets list pages for search, order, and page-size changes only", () => {
    const current = groupsListStateFromSearchParams(new URLSearchParams("page=4&page_size=40"));
    expect(withGroupsListChange(current, { q: "new" }).page).toBe(1);
    expect(withGroupsListChange(current, { ordering: "-name" }).page).toBe(1);
    expect(withGroupsListChange(current, { pageSize: 30 }).page).toBe(1);
    expect(withGroupsListChange(current, { page: 2 }, false).page).toBe(2);
  });

  it("normalizes detail tabs and removes Book-only state from Members", () => {
    const books = groupDetailStateFromSearchParams(new URLSearchParams(
      "q=storm&page_size=30&page=2&ordering=-series",
    ));
    expect(groupDetailSearchParams(books).toString()).toBe("ordering=-series&page=2&page_size=30&q=storm");
    expect(groupDetailPath("group/id", books)).toBe("/groups/group%2Fid?ordering=-series&page=2&page_size=30&q=storm");
    expect(groupBooksSdkQuery(books)).toEqual({ q: "storm", ordering: "-series", page: 2, pageSize: 30 });

    const members = withGroupDetailChange(books, { tab: "members" });
    expect(members).toMatchObject({ tab: "members", q: "", ordering: "title", page: 1, pageSize: 30 });
    expect(groupDetailSearchParams(members).toString()).toBe("tab=members&page_size=30");
    expect(groupMembersSdkQuery(members)).toEqual({ page: 1, pageSize: 30 });
    expect(groupDetailStateFromSearchParams(new URLSearchParams("tab=members&q=hidden&ordering=-author"))).toMatchObject({
      tab: "members", q: "", ordering: "title",
    });

    const shelves = withGroupDetailChange(books, { tab: "shelves" });
    expect(groupDetailSearchParams(shelves).toString()).toBe("tab=shelves&page_size=30");
    expect(groupShelvesSdkQuery("group/id", shelves)).toEqual({
      scope: "group", ownerGroupId: "group/id", ordering: "name", page: 1, pageSize: 30,
    });
    expect(groupDetailStateFromSearchParams(new URLSearchParams("tab=shelves&q=hidden&ordering=-author"))).toMatchObject({
      tab: "shelves", q: "", ordering: "title",
    });
  });
});
