import { describe, expect, it } from "vitest";

import { ApiError, type Page, type ShelvesQuery } from "@second-pass/spl-api";
import { loadPageWithRecovery } from "../app/routing/pageRecovery";
import { shelfBookBreadcrumbs, shelfDetailBreadcrumbFallback, shelvesListBreadcrumbFallback } from "../features/shelves/shelvesBreadcrumbs";

describe("Shelves orchestrator contracts", () => {
  it("uses no base breadcrumb and canonical detail and Book trails", () => {
    expect(shelvesListBreadcrumbFallback).toEqual([]);
    expect(shelfDetailBreadcrumbFallback("Favorites")).toEqual([
      { label: "Shelves", to: "/shelves", resetTrail: true },
      { label: "Favorites" },
    ]);
    expect(shelfBookBreadcrumbs("shelf/id", "Favorites", "Book", "/shelves/shelf%2Fid?ordering=title")).toEqual([
      { label: "Shelves", to: "/shelves", resetTrail: true },
      { label: "Favorites", to: "/shelves/shelf%2Fid?ordering=title" },
      { label: "Book" },
    ]);
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
