import { describe, expect, it } from "vitest";

import { ApiError, type LibraryGroupsQuery, type Page } from "@second-pass/spl-api";
import { groupBookBreadcrumbs, groupDetailBreadcrumbFallback, groupsListBreadcrumbFallback } from "../features/groups/groupsBreadcrumbs";
import { loadGroupPageWithRecovery } from "../features/groups/groupsPageRecovery";

describe("Groups orchestrator contracts", () => {
  it("uses no base breadcrumb and a canonical detail and Book trail", () => {
    expect(groupsListBreadcrumbFallback).toEqual([]);
    expect(groupDetailBreadcrumbFallback("Readers")).toEqual([
      { label: "Groups", to: "/groups", resetTrail: true },
      { label: "Readers" },
    ]);
    expect(groupBookBreadcrumbs("group/id", "Readers", "Book", "/groups/group%2Fid?q=book")).toEqual([
      { label: "Groups", to: "/groups", resetTrail: true },
      { label: "Readers", to: "/groups/group%2Fid?q=book" },
      { label: "Book" },
    ]);
  });

  it("recovers an out-of-range Group page once through page one", async () => {
    const calls: number[] = [];
    const query: LibraryGroupsQuery = { page: 8, pageSize: 20 };
    const request = async (candidate: LibraryGroupsQuery): Promise<Page<never>> => {
      calls.push(candidate.page!);
      if (candidate.page === 8) throw new ApiError("Invalid page.", 404);
      return { items: [], count: 45, next: null, previous: null };
    };
    const result = await loadGroupPageWithRecovery(query, request);
    expect(result.correctedPage).toBe(3);
    expect(calls).toEqual([8, 1, 3]);
  });

  it("does not reinterpret page-one or non-404 failures as pagination recovery", async () => {
    await expect(loadGroupPageWithRecovery(
      { page: 1, pageSize: 20 },
      async () => { throw new ApiError("Unavailable.", 404); },
    )).rejects.toThrow("Unavailable");
    await expect(loadGroupPageWithRecovery(
      { page: 2, pageSize: 20 },
      async () => { throw new ApiError("Broken.", 500); },
    )).rejects.toThrow("Broken");
  });
});
