import { describe, expect, it } from "vitest";

import {
  libraryAxisBasePath,
  libraryAxisSdkQuery,
  libraryBooksSdkQuery,
  libraryPath,
  libraryRequestView,
  librarySearchParams,
  libraryStateFromSearchParams,
  withLibraryChange,
  withLibrarySelectedContext,
} from "../features/library/libraryQuery";

const authorId = "11111111-1111-4111-8111-111111111111";
const seriesId = "22222222-2222-4222-8222-222222222222";

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

  it("discards malformed, foreign, and conflicting selected contexts with invalid values", () => {
    const state = libraryStateFromSearchParams(new URLSearchParams(`view=authors&author=a&series=${seriesId}&page=no&page_size=200&tag=hidden&q=++`));
    expect(state).toEqual({ view: "authors", tag: "hidden", ordering: "name", page: 1, pageSize: 20, q: "" });
    expect(librarySearchParams(state).toString()).toBe("view=authors&tag=hidden");
    expect(librarySearchParams(libraryStateFromSearchParams(new URLSearchParams(`author=${authorId}&series=${seriesId}`))).toString()).toBe("");
  });

  it("parses and serializes selected contexts in canonical order with context defaults omitted", () => {
    const author = libraryStateFromSearchParams(new URLSearchParams(`q=book&page_size=30&page=2&ordering=-series&tag=fantasy&author=${authorId}&view=authors`));
    expect(author).toMatchObject({ view: "authors", authorId, ordering: "-series" });
    expect(librarySearchParams(author).toString()).toBe(`view=authors&author=${authorId}&tag=fantasy&ordering=-series&page=2&page_size=30&q=book`);

    const series = libraryStateFromSearchParams(new URLSearchParams(`view=series&series=${seriesId}&ordering=series_index`));
    expect(series).toMatchObject({ view: "series", seriesId, ordering: "series_index" });
    expect(librarySearchParams(series).toString()).toBe(`view=series&series=${seriesId}`);
    expect(libraryStateFromSearchParams(new URLSearchParams(`view=authors&author=${authorId}&ordering=name`)).ordering).toBe("title");
    expect(libraryStateFromSearchParams(new URLSearchParams(`view=series&series=${seriesId}&ordering=name`)).ordering).toBe("series_index");
  });

  it("resets query changes and changes only page for paging", () => {
    const current = libraryStateFromSearchParams(new URLSearchParams("tag=old&ordering=-title&page=4&page_size=30&q=old"));
    for (const changes of [{ q: "new" }, { tag: "new" }, { ordering: "author" as const }, { pageSize: 40 }]) {
      expect(withLibraryChange(current, changes).page).toBe(1);
    }
    expect(withLibraryChange(current, { page: 2 }, false)).toEqual({ ...current, page: 2 });
  });

  it("builds every canonical axis base while preserving only non-default page size", () => {
    const filteredBooks = libraryStateFromSearchParams(new URLSearchParams("tag=old&ordering=-title&page=4&q=old"));
    expect(libraryAxisBasePath(filteredBooks, "books")).toBe("/library");

    const selectedAuthor = libraryStateFromSearchParams(new URLSearchParams(`view=authors&author=${authorId}&tag=old&ordering=-series&page=4&page_size=30&q=old`));
    expect(libraryAxisBasePath(selectedAuthor, "books")).toBe("/library?page_size=30");
    expect(libraryAxisBasePath(selectedAuthor, "authors")).toBe("/library?view=authors&page_size=30");

    const filteredAuthors = libraryStateFromSearchParams(new URLSearchParams(`view=authors&author=${authorId}&tag=old&ordering=-title&page=4&q=old`));
    expect(libraryAxisBasePath(filteredAuthors, "authors")).toBe("/library?view=authors");

    const selectedSeries = libraryStateFromSearchParams(new URLSearchParams(`view=series&series=${seriesId}&tag=old&ordering=-title&page=4&page_size=40&q=old`));
    expect(libraryAxisBasePath(selectedSeries, "series")).toBe("/library?view=series&page_size=40");

    const filteredSeries = libraryStateFromSearchParams(new URLSearchParams("view=series&tag=old&ordering=-book_count&page=4&q=old"));
    expect(libraryAxisBasePath(filteredSeries, "series")).toBe("/library?view=series");
  });

  it("enters and clears selected contexts while preserving only tag and page size", () => {
    const current = libraryStateFromSearchParams(new URLSearchParams("view=authors&tag=fantasy&ordering=-name&page=4&page_size=30&q=ada"));
    const selected = withLibrarySelectedContext(current, { kind: "author", id: authorId });
    expect(selected).toEqual({ view: "authors", authorId, tag: "fantasy", ordering: "title", page: 1, pageSize: 30, q: "" });
    expect(withLibrarySelectedContext(selected, undefined)).toEqual({ view: "authors", tag: "fantasy", ordering: "name", page: 1, pageSize: 30, q: "" });
    expect(libraryAxisBasePath(selected, "series")).toBe("/library?view=series&page_size=30");
  });

  it("composes selected context Book SDK filters with tag, search, ordering, and paging", () => {
    const author = libraryStateFromSearchParams(new URLSearchParams(`view=authors&author=${authorId}&tag=fantasy&ordering=-title&page=2&page_size=30&q=book`));
    expect(libraryBooksSdkQuery(author)).toEqual({ q: "book", tag: "fantasy", authorId, ordering: "-title", page: 2, pageSize: 30 });
    const series = libraryStateFromSearchParams(new URLSearchParams(`view=series&series=${seriesId}&tag=fantasy&page_size=40`));
    expect(libraryBooksSdkQuery(series)).toEqual({ tag: "fantasy", seriesId, ordering: "series_index", page: 1, pageSize: 40 });
    expect(libraryRequestView(author)).toBe("books");
    expect(libraryRequestView(series)).toBe("books");
  });

  it("builds preview-enabled SDK queries for Authors and Series without a tag", () => {
    const state = libraryStateFromSearchParams(new URLSearchParams("view=series&ordering=-name&page=2&page_size=30&q=saga&tag=ignored"));
    expect(libraryAxisSdkQuery(state)).toEqual({
      q: "saga", tag: "ignored", ordering: "-name", includePreviewBooks: true,
      previewLimit: 12, page: 2, pageSize: 30,
    });
  });
});
