import { ApiError, type BookPreview } from "@second-pass/spl-api";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { confirmAuthorSeriesDelete, isAttachedBookConflict } from "../features/library/authorSeriesDelete";
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

  it("renders a truthful cover preview with current Book Detail and Library-context links", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><AuthorSeriesAttachedBooksPageRegion
      kind="series"
      entityId="series/id"
      bookCount={6}
      books={books}
      breadcrumbTrail={[
        { label: "Library", to: "/library", icon: "library" },
        { label: "The Saga", to: "/library?view=series&series=series%2Fid", icon: "series" },
        { label: "Edit" },
      ]}
      editPath="/library/series/series%2Fid/edit"
    /></MemoryRouter>);

    expect(markup).toContain("Showing 2 of 6 attached Books.");
    expect(markup).toContain("/library/books/book%2Fone");
    expect(markup).toContain("No cover available for Missing Cover");
    expect(markup).toContain("/library?view=series&amp;series=series%2Fid");
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
