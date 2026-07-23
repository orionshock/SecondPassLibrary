import { describe, expect, it } from "vitest";

import {
  libraryBooksSdkQuery,
  libraryPath,
  librarySearchParams,
  libraryStateFromSearchParams,
  withLibraryChange,
} from "../features/library/libraryQuery";

describe("Library URL state", () => {
  it("omits every default from the canonical URL", () => {
    const state = libraryStateFromSearchParams(new URLSearchParams());
    expect(librarySearchParams(state).toString()).toBe("");
    expect(libraryPath(state)).toBe("/library");
    expect(libraryBooksSdkQuery(state)).toEqual({ ordering: "title", page: 1, pageSize: 20 });
  });

  it("uses canonical tag, ordering, page, page_size, q order without a slash before the query", () => {
    const state = libraryStateFromSearchParams(new URLSearchParams("q=chaos&page_size=40&page=3&ordering=-series&tag=philosophy"));
    expect(librarySearchParams(state).toString()).toBe("tag=philosophy&ordering=-series&page=3&page_size=40&q=chaos");
    expect(libraryPath(state)).toBe("/library?tag=philosophy&ordering=-series&page=3&page_size=40&q=chaos");
  });

  it("normalizes unsupported first-slice axes, filters, and invalid values", () => {
    const state = libraryStateFromSearchParams(new URLSearchParams("view=authors&author=a&series=s&page=no&page_size=200&ordering=publisher&q=++"));
    expect(state).toEqual({ view: "books", ordering: "title", page: 1, pageSize: 20, q: "" });
    expect(librarySearchParams(state).toString()).toBe("");
  });

  it("resets page for query changes and changes only page for paging", () => {
    const current = libraryStateFromSearchParams(new URLSearchParams("tag=old&ordering=-title&page=4&page_size=30&q=old"));
    for (const changes of [{ q: "new" }, { tag: "new" }, { ordering: "author" as const }, { pageSize: 40 }]) {
      expect(withLibraryChange(current, changes).page).toBe(1);
    }
    expect(withLibraryChange(current, { page: 2 }, false)).toEqual({ ...current, page: 2 });
  });
});
