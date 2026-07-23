import { describe, expect, it } from "vitest";

import {
  libraryAxisSdkQuery,
  libraryBooksSdkQuery,
  libraryPath,
  librarySearchParams,
  libraryStateFromSearchParams,
  withLibraryChange,
  withLibraryView,
} from "../features/library/libraryQuery";

describe("Library URL state", () => {
  it("omits every Books default from the canonical URL", () => {
    const state = libraryStateFromSearchParams(new URLSearchParams());
    expect(librarySearchParams(state).toString()).toBe("");
    expect(libraryPath(state)).toBe("/library");
    expect(libraryBooksSdkQuery(state)).toEqual({ ordering: "title", page: 1, pageSize: 20 });
  });

  it("serializes each non-default view first and uses canonical query order", () => {
    const authors = libraryStateFromSearchParams(new URLSearchParams("q=ada&page_size=40&page=3&ordering=-book_count&view=authors&tag=ignored"));
    expect(librarySearchParams(authors).toString()).toBe("view=authors&tag=ignored&ordering=-book_count&page=3&page_size=40&q=ada");
    expect(libraryPath(authors)).toBe("/library?view=authors&tag=ignored&ordering=-book_count&page=3&page_size=40&q=ada");
    expect(librarySearchParams(libraryStateFromSearchParams(new URLSearchParams("view=series"))).toString()).toBe("view=series");

    const books = libraryStateFromSearchParams(new URLSearchParams("q=chaos&page_size=40&page=3&ordering=-series&tag=philosophy"));
    expect(librarySearchParams(books).toString()).toBe("tag=philosophy&ordering=-series&page=3&page_size=40&q=chaos");
  });

  it("omits per-axis ordering defaults and normalizes invalid ordering for the active axis", () => {
    expect(librarySearchParams(libraryStateFromSearchParams(new URLSearchParams("view=authors&ordering=name"))).toString()).toBe("view=authors");
    expect(libraryStateFromSearchParams(new URLSearchParams("view=authors&ordering=title")).ordering).toBe("name");
    expect(libraryStateFromSearchParams(new URLSearchParams("ordering=book_count")).ordering).toBe("title");
    expect(libraryStateFromSearchParams(new URLSearchParams("view=series&ordering=publisher")).ordering).toBe("name");
  });

  it("discards unsupported selected contexts and invalid values", () => {
    const state = libraryStateFromSearchParams(new URLSearchParams("view=authors&author=a&series=s&page=no&page_size=200&tag=hidden&q=++"));
    expect(state).toEqual({ view: "authors", tag: "hidden", ordering: "name", page: 1, pageSize: 20, q: "" });
    expect(librarySearchParams(state).toString()).toBe("view=authors&tag=hidden");
  });

  it("resets query changes, changes only page for paging, and resets axes while preserving page size", () => {
    const current = libraryStateFromSearchParams(new URLSearchParams("tag=old&ordering=-title&page=4&page_size=30&q=old"));
    for (const changes of [{ q: "new" }, { tag: "new" }, { ordering: "author" as const }, { pageSize: 40 }]) {
      expect(withLibraryChange(current, changes).page).toBe(1);
    }
    expect(withLibraryChange(current, { page: 2 }, false)).toEqual({ ...current, page: 2 });
    expect(withLibraryView(current, "authors")).toEqual({ view: "authors", tag: "old", ordering: "name", page: 1, pageSize: 30, q: "" });
  });

  it("builds preview-enabled SDK queries for Authors and Series without a tag", () => {
    const state = libraryStateFromSearchParams(new URLSearchParams("view=series&ordering=-name&page=2&page_size=30&q=saga&tag=ignored"));
    expect(libraryAxisSdkQuery(state)).toEqual({ q: "saga", tag: "ignored", ordering: "-name", includePreviewBooks: true, page: 2, pageSize: 30 });
  });
});
