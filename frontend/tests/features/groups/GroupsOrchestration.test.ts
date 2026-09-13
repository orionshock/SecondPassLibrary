import { describe, expect, it } from "vitest";

import { groupBookBreadcrumbs, groupDetailBreadcrumbFallback, groupShelfBookBreadcrumbs, groupShelfBreadcrumbs, groupShelfEditBreadcrumbs, groupsListBreadcrumbFallback } from "../../../src/features/groups/groupsBreadcrumbs";

describe("Groups orchestrator contracts", () => {
  it("uses no base breadcrumb and a canonical detail and Book trail", () => {
    expect(groupsListBreadcrumbFallback).toEqual([]);
    expect(groupDetailBreadcrumbFallback("Readers")).toEqual([
      { label: "Groups", to: "/groups", resetTrail: true, icon: "group" },
      { label: "Readers", icon: "group" },
    ]);
    expect(groupBookBreadcrumbs("group/id", "Readers", "Book", "/groups/group%2Fid?q=book")).toEqual([
      { label: "Groups", to: "/groups", resetTrail: true, icon: "group" },
      { label: "Readers", to: "/groups/group%2Fid?q=book", icon: "group" },
      { label: "Book", icon: "book" },
    ]);
    expect(groupShelfBreadcrumbs("group/id", "Readers", "Favorites", "/groups/group%2Fid?tab=shelves")).toEqual([
      { label: "Groups", to: "/groups", resetTrail: true, icon: "group" },
      { label: "Readers", to: "/groups/group%2Fid", icon: "group" },
      { label: "Shelves", to: "/groups/group%2Fid?tab=shelves", icon: "shelf" },
      { label: "Favorites", icon: "shelf" },
    ]);
    expect(groupShelfBookBreadcrumbs(
      "group/id", "Readers", "shelf/id", "Favorites", "Book", "/groups/group%2Fid?tab=shelves",
    )).toEqual([
      { label: "Groups", to: "/groups", resetTrail: true, icon: "group" },
      { label: "Readers", to: "/groups/group%2Fid", icon: "group" },
      { label: "Shelves", to: "/groups/group%2Fid?tab=shelves", icon: "shelf" },
      { label: "Favorites", to: "/shelves/shelf%2Fid", icon: "shelf" },
      { label: "Book", icon: "book" },
    ]);
    expect(groupShelfEditBreadcrumbs(
      "group/id", "Readers", "shelf/id", "Favorites", "/groups/group%2Fid?tab=shelves",
    ).slice(-2)).toEqual([
      { label: "Favorites", to: "/shelves/shelf%2Fid", icon: "shelf" },
      { label: "Edit" },
    ]);
    expect(groupDetailBreadcrumbFallback("Common Room", true)[1]).toEqual({ label: "Common Room", icon: "public-group" });
  });

});
