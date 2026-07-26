import { describe, expect, it } from "vitest";

import { ApiError, type LibraryGroupsQuery, type Page } from "@second-pass/spl-api";
import { loadPageWithRecovery } from "../app/routing/pageRecovery";
import { groupBookBreadcrumbs, groupDetailBreadcrumbFallback, groupShelfBreadcrumbs, groupsListBreadcrumbFallback } from "../features/groups/groupsBreadcrumbs";

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
    expect(groupShelfBreadcrumbs("group/id", "Readers", "Favorites", "/groups/group%2Fid?tab=shelves")).toEqual([
      { label: "Groups", to: "/groups", resetTrail: true },
      { label: "Readers", to: "/groups/group%2Fid" },
      { label: "Shelves", to: "/groups/group%2Fid?tab=shelves" },
      { label: "Favorites" },
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
    const result = await loadPageWithRecovery({
      requestedPage: query.page ?? 1,
      pageSize: query.pageSize ?? 20,
      recoveryKey: "groups",
      recoveredKeys: new Set<string>(),
      fetchPage: (page) => request({ ...query, page }),
      buildRecoveredLocation: (page) => `page=${page}`,
      replaceLocation: () => undefined,
    });
    expect(result.correctedPage).toBe(3);
    expect(calls).toEqual([8, 1, 3]);
  });

});
