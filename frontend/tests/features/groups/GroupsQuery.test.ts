import { describe, expect, it } from "vitest";

import {
  groupBooksSdkQuery,
  groupDetailPath,
  groupDetailSearchParams,
  groupDetailStateFromSearchParams,
  groupEditQueryDuringImmediateMutation,
  groupEditQueryFromSearchParams,
  groupEditQueryWithPage,
  groupEditSearchParams,
  groupMembersSdkQuery,
  groupShelvesSdkQuery,
  groupsListPath,
  groupsListSdkQuery,
  groupsListSearchParams,
  groupsListStateFromSearchParams,
  withGroupDetailChange,
  withGroupsListChange,
} from "../../../src/features/groups/groupsQuery";

describe("Groups URL state", () => {
  it("normalizes Group list defaults and uses canonical query order", () => {
    const defaults = groupsListStateFromSearchParams(new URLSearchParams());
    expect(groupsListPath(defaults)).toBe("/groups");
    expect(groupsListSdkQuery(defaults)).toEqual({
      ordering: "name", includePreviewBooks: true, previewLimit: 12, page: 1, pageSize: 20,
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
      scope: "group", ownerGroupId: "group/id", ordering: "name", includePreviewBooks: true,
      previewLimit: 12, page: 1, pageSize: 30,
    });
    expect(groupDetailStateFromSearchParams(new URLSearchParams("tab=shelves&q=hidden&ordering=-author"))).toMatchObject({
      tab: "shelves", q: "", ordering: "title",
    });
  });

  it("keeps Group management tabs URL-backed with one universal Details default", () => {
    expect(groupEditQueryFromSearchParams(new URLSearchParams())).toEqual({
      tab: "details", query: "", page: 1, pageSize: 20,
    });
    expect(groupEditQueryFromSearchParams(new URLSearchParams("trail=context&tab=books"))).toEqual({
      tab: "books", query: "trail=context&tab=books", page: 1, pageSize: 20,
    });
    expect(groupEditQueryFromSearchParams(new URLSearchParams("tab=add-books"))).toEqual({
      tab: "add-books", query: "tab=add-books", page: 1, pageSize: 20,
    });
    expect(groupEditQueryFromSearchParams(new URLSearchParams("tab=members"))).toEqual({
      tab: "members", query: "tab=members", page: 1, pageSize: 20,
    });
    expect(groupEditQueryFromSearchParams(new URLSearchParams("trail=context&tab=unknown"))).toEqual({
      tab: "details", query: "trail=context", page: 1, pageSize: 20,
    });
    const paged = groupEditQueryFromSearchParams(new URLSearchParams(
      "trail=context&tab=books&page=4&page_size=40",
    ));
    expect(paged).toMatchObject({ tab: "books", page: 4, pageSize: 40 });
    expect(groupEditQueryWithPage(paged, { page: 2 })).toBe("trail=context&tab=books&page=2&page_size=40");
    expect(groupEditQueryWithPage(paged, { pageSize: 30 })).toBe("trail=context&tab=books&page_size=30");
    expect(groupEditSearchParams(new URLSearchParams("trail=context&tab=members"), "details").toString())
      .toBe("trail=context");
  });

  it("freezes the last safe Group management query during immediate mutations", () => {
    const stable = groupEditQueryFromSearchParams(new URLSearchParams("trail=context&tab=members"));
    const requested = groupEditQueryFromSearchParams(new URLSearchParams("trail=context&tab=books"));
    expect(groupEditQueryDuringImmediateMutation(requested, stable, true)).toBe(stable);
    expect(groupEditQueryDuringImmediateMutation(requested, stable, false)).toBe(requested);
  });
});
