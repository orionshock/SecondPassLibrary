import { ApiError, type BookPreview, type CompactBook } from "@second-pass/spl-api";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { confirmAuthorSeriesDelete, isAttachedBookConflict } from "../features/library/authorSeriesDelete";
import { AttachedBooksRequestGate, appendAttachedBooks, attachedBooksQuery } from "../features/library/authorSeriesAttachedBooks";
import { AuthorSeriesAttachedBooksPageRegion } from "../features/library/regions/AuthorSeriesAttachedBooksPageRegion";
import { AuthorSeriesDangerZonePageRegion } from "../features/library/regions/AuthorSeriesDangerZonePageRegion";
import { AuthorSeriesEditFormPageRegion } from "../features/library/regions/AuthorSeriesEditFormPageRegion";

const books: BookPreview[] = [
  { id: "book/one", title: "A very long attached Book title that remains linked", coverUrl: "/media/one.jpg" },
  { id: "book-two", title: "Missing Cover", coverUrl: null },
];

describe("Author and Series deletion presentation", () => {
  it("leaves the ordinary edit form and save controls intact", () => {
    const markup = renderToStaticMarkup(<AuthorSeriesEditFormPageRegion
      kind="author"
      draft={{ name: "Ada", sortName: "Author, Ada", prose: "Biography" }}
      state={{ pending: false }}
      onChange={vi.fn()}
      onSubmit={vi.fn()}
      onCancel={vi.fn()}
    />);

    expect(markup).toContain("Save Author");
    expect(markup).toContain("Biography");
    expect(markup).not.toContain("Delete Author");
  });

  it("blocks attached Author deletion with an accessible reason and bounded error", () => {
    const markup = renderToStaticMarkup(<AuthorSeriesDangerZonePageRegion
      kind="author"
      name="Ada Author"
      bookCount={25}
      state={{ pending: false, error: new Error("Author deletion is no longer available.") }}
      onDelete={vi.fn()}
    />);

    expect(markup).toContain("Author cannot be deleted because 25 Books are attached.");
    expect(markup).toContain('aria-describedby="author-delete-availability"');
    expect(markup).toContain("disabled");
    expect(markup).toContain('role="alert"');
    expect(markup).not.toContain("Series cannot");
  });

  it("enables unattached Series deletion and exposes pending duplicate protection", () => {
    const ready = renderToStaticMarkup(<AuthorSeriesDangerZonePageRegion
      kind="series"
      name="The Saga"
      bookCount={0}
      state={{ pending: false }}
      onDelete={vi.fn()}
    />);
    const pending = renderToStaticMarkup(<AuthorSeriesDangerZonePageRegion
      kind="series"
      name="The Saga"
      bookCount={0}
      state={{ pending: true }}
      onDelete={vi.fn()}
    />);

    expect(ready).toContain("No Books are attached to The Saga. Deletion is available.");
    expect(ready).not.toContain("disabled");
    expect(pending).toContain("Deleting...");
    expect(pending).toContain("disabled");
    expect(ready).not.toContain("Author cannot");
  });

  it("renders a truthful cover-only grid with accessible Book and Library-context links", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><AuthorSeriesAttachedBooksPageRegion
      kind="series"
      entityId="series/id"
      bookCount={6}
      books={books}
      loadedTotal={6}
      pending={false}
      hasMore={true}
      breadcrumbTrail={[
        { label: "Library", to: "/library", icon: "library" },
        { label: "The Saga", to: "/library?view=series&series=series%2Fid", icon: "series" },
        { label: "Edit" },
      ]}
      editPath="/library/series/series%2Fid/edit"
      onLoadMore={vi.fn()}
      onRetry={vi.fn()}
    /></MemoryRouter>);

    expect(markup).toContain("Showing 2 of 6 attached Books.");
    expect(markup).toContain("/library/books/book%2Fone");
    expect(markup).toContain('aria-label="View A very long attached Book title that remains linked"');
    expect(markup).toContain("No cover available for Missing Cover");
    expect(markup).toContain("/library?view=series&amp;series=series%2Fid");
    expect(markup).toContain("Load more");
    expect(markup).not.toContain("book-row-component");
    expect(markup.replace(/<[^>]+>/g, "")).not.toContain("A very long attached Book title");
  });

  it("announces local loading and retry states without removing loaded covers", () => {
    const loading = renderToStaticMarkup(<MemoryRouter><AuthorSeriesAttachedBooksPageRegion
      kind="author" entityId="author" bookCount={3} books={books} loadedTotal={3}
      pending={true} hasMore={true} breadcrumbTrail={[]} editPath="/library/authors/author/edit"
      onLoadMore={vi.fn()} onRetry={vi.fn()}
    /></MemoryRouter>);
    const failed = renderToStaticMarkup(<MemoryRouter><AuthorSeriesAttachedBooksPageRegion
      kind="author" entityId="author" bookCount={3} books={books} loadedTotal={3}
      pending={false} error={new Error("Could not load another page.")} hasMore={true}
      breadcrumbTrail={[]} editPath="/library/authors/author/edit"
      onLoadMore={vi.fn()} onRetry={vi.fn()}
    /></MemoryRouter>);

    expect(loading).toContain("Loading attached Books");
    expect(loading).toContain("/library/books/book%2Fone");
    expect(loading).toContain("disabled");
    expect(failed).toContain("Could not load another page.");
    expect(failed).toContain("Retry");
    expect(failed).toContain("/library/books/book%2Fone");

    const complete = renderToStaticMarkup(<MemoryRouter><AuthorSeriesAttachedBooksPageRegion
      kind="author" entityId="author" bookCount={2} books={books} loadedTotal={2}
      pending={false} hasMore={false} breadcrumbTrail={[]} editPath="/library/authors/author/edit"
      onLoadMore={vi.fn()} onRetry={vi.fn()}
    /></MemoryRouter>);
    expect(complete).toContain("All 2 attached Books are loaded.");
    expect(complete).not.toContain("Load more");
  });

  it("uses deterministic attached-Book queries and appends pages without duplicates", () => {
    expect(attachedBooksQuery("author", "author/id", 1)).toEqual({
      authorId: "author/id", ordering: "title", page: 1, pageSize: 24,
    });
    expect(attachedBooksQuery("series", "series/id", 2)).toEqual({
      seriesId: "series/id", ordering: "series_index", page: 2, pageSize: 24,
    });
    const page = [
      { id: "book-two", title: "Updated title", coverUrl: "/replacement.jpg" },
      { id: "book-three", title: "Third", coverUrl: null },
    ] as CompactBook[];

    expect(appendAttachedBooks(books, page)).toEqual([
      books[0], books[1], { id: "book-three", title: "Third", coverUrl: null },
    ]);
  });

  it("blocks duplicate page requests and invalidates stale entity requests", () => {
    const gate = new AttachedBooksRequestGate();
    gate.reset("author:first");

    expect(gate.start("author:first")).toBe(true);
    expect(gate.start("author:first")).toBe(false);
    gate.reset("series:second");
    expect(gate.isCurrent("author:first")).toBe(false);
    expect(gate.start("author:first")).toBe(false);
    expect(gate.start("series:second")).toBe(true);
    gate.finish("series:second");
    expect(gate.start("series:second")).toBe(true);
  });

  it("requires explicit entity-named confirmation and preserves cancel behavior", () => {
    const cancel = vi.fn((_message: string) => false);
    const confirm = vi.fn((_message: string) => true);

    expect(confirmAuthorSeriesDelete("author", "Ada Author", cancel)).toBe(false);
    expect(confirmAuthorSeriesDelete("series", "The Saga", confirm)).toBe(true);
    expect(cancel).toHaveBeenCalledOnce();
    expect(cancel.mock.calls[0]?.[0]).toContain("Author “Ada Author”");
    expect(confirm.mock.calls[0]?.[0]).toContain("Series “The Saga”");
  });

  it("recognizes only the entity-specific canonical late-attachment conflict", () => {
    expect(isAttachedBookConflict(
      new ApiError("Attached.", 409, { code: "author_has_books" }),
      "author",
    )).toBe(true);
    expect(isAttachedBookConflict(
      new ApiError("Attached.", 409, { code: "series_has_books" }),
      "author",
    )).toBe(false);
  });
});
