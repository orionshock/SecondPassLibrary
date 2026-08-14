import { describe, expect, it, vi } from "vitest";

import { ApiError, type CompactBook, type LibraryAxisQuery, type LibraryBooksQuery, type Page } from "@second-pass/spl-api";
import { appRoutes, sectionRoutes } from "../app/router";
import { loadPageWithRecovery } from "../app/routing/pageRecovery";
import { catalogLayoutStabilityKey, libraryBreadcrumbFallback, loadSelectedLibraryContextDetails, unknownCatalogTag } from "../features/library/browse/LibraryOrchestrator";
import type { LibraryUrlState } from "../features/library/libraryQuery";

const page = (count: number): Page<CompactBook> => ({ items: [], count, next: null, previous: null });

function recoverLibraryPage<Item, Query extends { page?: number; pageSize?: number }>(
  query: Query,
  request: (query: Query) => Promise<Page<Item>>,
) {
  return loadPageWithRecovery({
    requestedPage: query.page ?? 1,
    pageSize: query.pageSize ?? 20,
    recoveryKey: JSON.stringify(query),
    recoveredKeys: new Set<string>(),
    fetchPage: (requestedPage) => request({ ...query, page: requestedPage }),
    buildRecoveredLocation: (requestedPage) => `page=${requestedPage}`,
    replaceLocation: () => undefined,
  });
}

describe("Library Orchestrator contracts", () => {
  it("registers the Books axis and bounded Book placeholder as real routes", () => {
    const routes = appRoutes[0].children;
    expect(routes.some((route) => route.path === "library")).toBe(true);
    expect(routes.some((route) => route.path === "library/books/:bookId")).toBe(true);
    expect(sectionRoutes.map(({ path }): string => path)).not.toContain("library");
    expect(libraryBreadcrumbFallback).toEqual([]);
  });

  it("recovers a page-not-found once through page one and the computed final page", async () => {
    const calls: LibraryBooksQuery[] = [];
    const request = async (query: LibraryBooksQuery) => {
      calls.push(query);
      if (query.page === 9) throw new ApiError("Invalid page.", 404);
      return page(query.page === 1 ? 45 : 45);
    };
    const result = await recoverLibraryPage({ q: "title", page: 9, pageSize: 20 } satisfies LibraryBooksQuery, request);
    expect(result.correctedPage).toBe(3);
    expect(calls.map(({ page }) => page)).toEqual([9, 1, 3]);
  });

  it("uses the same bounded out-of-range recovery for Author and Series queries", async () => {
    for (const expectedLastPage of [2, 4]) {
      const calls: number[] = [];
      const query: LibraryAxisQuery = { includePreviewBooks: true, page: 8, pageSize: 20 };
      const result = await recoverLibraryPage(query, async (requestQuery) => {
        calls.push(requestQuery.page!);
        if (requestQuery.page === 8) throw new ApiError("Invalid page.", 404);
        return { items: [], count: expectedLastPage * 20, next: null, previous: null };
      });
      expect(result.correctedPage).toBe(expectedLastPage);
      expect(calls).toEqual([8, 1, expectedLastPage]);
    }
  });

  it("clears an unknown active Catalog Tag only after the full tag list succeeds", () => {
    expect(unknownCatalogTag("missing", undefined)).toBe(false);
    expect(unknownCatalogTag("missing", [{ id: "tag", name: "Fantasy", slug: "fantasy", bookCount: 2 }])).toBe(true);
    expect(unknownCatalogTag("fantasy", [{ id: "tag", name: "Fantasy", slug: "fantasy", bookCount: 2 }])).toBe(false);
  });

  it("retains Catalog height between Book pages but resets it for a changed result set", () => {
    const state: LibraryUrlState = { view: "books", page: 1, pageSize: 20, q: "", ordering: "title" };
    const laterPage: LibraryUrlState = { ...state, page: 3 };
    const firstPage = catalogLayoutStabilityKey("books", state);
    expect(catalogLayoutStabilityKey("books", laterPage)).toBe(firstPage);
    expect(catalogLayoutStabilityKey("books", { ...state, q: "history" })).not.toBe(firstPage);
    expect(catalogLayoutStabilityKey("books", { ...state, pageSize: 40 })).not.toBe(firstPage);
  });

  it("loads role-scoped selected Author and Series details through their existing SDK boundaries", async () => {
    const author = vi.fn(async (id: string) => ({ id, name: "Author Name", sortName: "Name, Author", biography: "Biography", bookCount: 2 }));
    const series = vi.fn(async (id: string) => ({ id, name: "Series Name", sortName: "Series Name", summary: "Summary", bookCount: 3 }));

    await expect(loadSelectedLibraryContextDetails("author", "author-id", { author, series })).resolves.toEqual({
      kind: "author", id: "author-id", name: "Author Name", bookCount: 2, blurb: "Biography",
    });
    await expect(loadSelectedLibraryContextDetails("series", "series-id", { author, series })).resolves.toEqual({
      kind: "series", id: "series-id", name: "Series Name", bookCount: 3, blurb: "Summary",
    });
    expect(author).toHaveBeenCalledWith("author-id");
    expect(series).toHaveBeenCalledWith("series-id");
  });
});
