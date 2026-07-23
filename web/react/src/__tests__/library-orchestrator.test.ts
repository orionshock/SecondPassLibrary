import { describe, expect, it } from "vitest";

import { ApiError, type CompactBook, type LibraryAxisQuery, type LibraryBooksQuery, type Page } from "@second-pass/spl-api";
import { appRoutes, sectionRoutes } from "../app/router";
import { libraryBreadcrumbFallback, loadBooksWithPageRecovery, loadLibraryPageWithRecovery } from "../features/library/LibraryOrchestrator";

const page = (count: number): Page<CompactBook> => ({ items: [], count, next: null, previous: null });

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
    const result = await loadBooksWithPageRecovery({ q: "title", page: 9, pageSize: 20 }, request);
    expect(result.correctedPage).toBe(3);
    expect(calls.map(({ page }) => page)).toEqual([9, 1, 3]);
  });

  it("does not recover arbitrary page-one 404 responses or non-pagination errors", async () => {
    const request = async () => { throw new ApiError("Not found.", 404); };
    await expect(loadBooksWithPageRecovery({ page: 1, pageSize: 20 }, request)).rejects.toThrow("Not found");
    await expect(loadBooksWithPageRecovery({ page: 2, pageSize: 20 }, async () => { throw new ApiError("Broken.", 500); })).rejects.toThrow("Broken");
  });

  it("uses the same bounded out-of-range recovery for Author and Series queries", async () => {
    for (const expectedLastPage of [2, 4]) {
      const calls: number[] = [];
      const query: LibraryAxisQuery = { includePreviewBooks: true, page: 8, pageSize: 20 };
      const result = await loadLibraryPageWithRecovery(query, async (requestQuery) => {
        calls.push(requestQuery.page!);
        if (requestQuery.page === 8) throw new ApiError("Invalid page.", 404);
        return { items: [], count: expectedLastPage * 20, next: null, previous: null };
      });
      expect(result.correctedPage).toBe(expectedLastPage);
      expect(calls).toEqual([8, 1, expectedLastPage]);
    }
  });
});
