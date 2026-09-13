import { describe, expect, it, vi } from "vitest";

import { appRoutes, sectionRoutes } from "../../../../src/app/router";
import { catalogLayoutStabilityKey, libraryBreadcrumbFallback, loadSelectedLibraryContextDetails, resultCatalogTags, unknownCatalogTag } from "../../../../src/features/library/browse/LibraryOrchestrator";
import type { LibraryUrlState } from "../../../../src/features/library/libraryQuery";

describe("Library Orchestrator contracts", () => {
  it("registers the Books axis and bounded Book placeholder as real routes", () => {
    const routes = appRoutes[0].children;
    expect(routes.some((route) => route.path === "library")).toBe(true);
    expect(routes.some((route) => route.path === "library/books/:bookId")).toBe(true);
    expect(sectionRoutes.map(({ path }): string => path)).not.toContain("library");
    expect(libraryBreadcrumbFallback).toEqual([]);
  });

  it("clears an unknown active Catalog Tag only after the full tag list succeeds", () => {
    expect(unknownCatalogTag("missing", undefined)).toBe(false);
    expect(unknownCatalogTag("missing", [{ id: "tag", name: "Fantasy", slug: "fantasy", bookCount: 2 }])).toBe(true);
    expect(unknownCatalogTag("fantasy", [{ id: "tag", name: "Fantasy", slug: "fantasy", bookCount: 2 }])).toBe(false);
  });

  it("uses contextual Catalog Tag counts for every result context and scope totals while loading", () => {
    const scope = [{ id: "scope", name: "Scope", slug: "scope", bookCount: 9 }];
    const books = [{ id: "book", name: "Book", slug: "book", bookCount: 3 }];
    const authors = [{ id: "author", name: "Author", slug: "author", bookCount: 2 }];
    const series = [{ id: "series", name: "Series", slug: "series", bookCount: 1 }];
    const loads = {
      books: { loading: false, page: { catalogTags: books } },
      authors: { loading: false, page: { catalogTags: authors } },
      series: { loading: false, page: { catalogTags: series } },
    };

    expect(resultCatalogTags("books", loads, scope)).toBe(books);
    expect(resultCatalogTags("authors", loads, scope)).toBe(authors);
    expect(resultCatalogTags("series", loads, scope)).toBe(series);
    expect(resultCatalogTags("books", { ...loads, books: { ...loads.books, loading: true } }, scope)).toBe(scope);
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
