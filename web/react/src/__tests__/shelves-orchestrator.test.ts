import { describe, expect, it } from "vitest";

import { ApiError, type Page, type ShelvesQuery } from "@second-pass/spl-api";
import { appendBreadcrumbTrail, breadcrumbNavigationState, readIncomingBreadcrumbTrail } from "../app/navigation/breadcrumbs";
import { loadPageWithRecovery } from "../app/routing/pageRecovery";
import { bookEditBreadcrumbTrail } from "../features/library/bookDetailPresentation";
import { shelfBookBreadcrumbs, shelfDetailBreadcrumbFallback, shelvesListBreadcrumbFallback } from "../features/shelves/shelvesBreadcrumbs";
import {
  shelfScopeBreadcrumb,
  shelfScopeFromBreadcrumbState,
  shelfScopeFromSummary,
  shelfScopePath,
  validBreadcrumbStateForShelf,
} from "../features/shelves/shelfScopes";

describe("Shelves orchestrator contracts", () => {
  it("uses canonical Shelf scope destinations in detail and Book trails", () => {
    expect(shelvesListBreadcrumbFallback).toEqual([]);
    expect(shelfDetailBreadcrumbFallback("shared", "Favorites")).toEqual([
      { label: "Shelves", to: "/shelves", resetTrail: true, icon: "shelf" },
      { label: "Shared by Others", to: "/shelves?scope=shared", icon: "shared-shelf" },
      { label: "Favorites", icon: "shelf" },
    ]);
    expect(shelfBookBreadcrumbs("group", "shelf/id", "Favorites", "Book", "/shelves/shelf%2Fid?ordering=title")).toEqual([
      { label: "Shelves", to: "/shelves", resetTrail: true, icon: "shelf" },
      { label: "Group Shelves", to: "/shelves?scope=group", icon: "group-shelf" },
      { label: "Favorites", to: "/shelves/shelf%2Fid?ordering=title", icon: "shelf" },
      { label: "Book", icon: "book" },
    ]);
  });

  it("derives truthful direct-route scope without a feature flag", () => {
    expect(shelfScopePath("personal")).toBe("/shelves");
    expect(shelfScopePath("shared")).toBe("/shelves?scope=shared");
    expect(shelfScopePath("group")).toBe("/shelves?scope=group");
    expect(shelfScopeFromSummary({ ownerType: "user", canEdit: true })).toBe("personal");
    expect(shelfScopeFromSummary({ ownerType: "user", canEdit: false })).toBe("shared");
    expect(shelfScopeFromSummary({ ownerType: "group", canEdit: false })).toBe("group");
  });

  it("round-trips scope context without duplication and keeps breadcrumb bounds", () => {
    const groupScope = shelfScopeBreadcrumb("group");
    const state = breadcrumbNavigationState([
      { label: "Shelves", to: "/shelves", resetTrail: true, icon: "shelf" },
      groupScope,
      { label: "Favorites", icon: "shelf" },
    ]);
    expect(shelfScopeFromBreadcrumbState(state)).toBe("group");
    expect(readIncomingBreadcrumbTrail(state)?.filter(({ icon }) => icon === "group-shelf")).toHaveLength(1);
    expect(validBreadcrumbStateForShelf(state, { ownerType: "group", canEdit: false })).toBe(state);
    expect(validBreadcrumbStateForShelf(state, { ownerType: "user", canEdit: true })).toBeUndefined();

    let trail = shelfBookBreadcrumbs("group", "shelf", "Favorites", "Book");
    for (let index = 0; index < 12; index += 1) {
      trail = appendBreadcrumbTrail(trail, { label: `Context ${index}` });
    }
    expect(trail).toHaveLength(12);
    expect(trail[0]?.label).toBe("Shelves");
    expect(trail.at(-1)?.label).toBe("Context 11");
  });

  it("keeps Shelf scope when Book routing extends the trail", () => {
    const bookTrail = shelfBookBreadcrumbs("shared", "shelf", "Favorites", "Book");
    const editTrail = bookEditBreadcrumbTrail(bookTrail, "book", "Book");
    expect(editTrail.map(({ label }) => label)).toEqual([
      "Shelves", "Shared by Others", "Favorites", "Book", "Edit",
    ]);
    expect(editTrail.filter(({ icon }) => icon === "shared-shelf")).toHaveLength(1);
  });

  it("recovers a bounded out-of-range Shelf page through page one", async () => {
    const calls: number[] = [];
    const query: ShelvesQuery = { page: 8, pageSize: 20 };
    const request = async (candidate: ShelvesQuery): Promise<Page<never>> => {
      calls.push(candidate.page!);
      if (candidate.page === 8) throw new ApiError("Invalid page.", 404);
      return { items: [], count: 45, next: null, previous: null };
    };
    const result = await loadPageWithRecovery({
      requestedPage: query.page ?? 1,
      pageSize: query.pageSize ?? 20,
      recoveryKey: "shelves",
      recoveredKeys: new Set<string>(),
      fetchPage: (page) => request({ ...query, page }),
      buildRecoveredLocation: (page) => `page=${page}`,
      replaceLocation: () => undefined,
    });
    expect(result.correctedPage).toBe(3);
    expect(calls).toEqual([8, 1, 3]);
  });

});
