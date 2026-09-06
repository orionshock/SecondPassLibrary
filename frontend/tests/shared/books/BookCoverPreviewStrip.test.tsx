import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { BookCoverPreviewStrip } from "../../../src/shared/books/BookCoverPreviewStrip";
import { COMPACT_BOOK_COVER_PREVIEW_SOURCE_LIMIT } from "../../../src/shared/books/bookCoverPreview";

describe("BookCoverPreviewStrip", () => {
  it("keeps a bounded interactive source list without imposing the old six-cover render cap", () => {
    const books = Array.from({ length: COMPACT_BOOK_COVER_PREVIEW_SOURCE_LIMIT + 2 }, (_, index) => ({
      id: `book-${index + 1}`,
      title: `Book ${index + 1}`,
      coverUrl: null,
      href: `/library/books/book-${index + 1}`,
    }));
    const markup = renderToStaticMarkup(<MemoryRouter>
      <BookCoverPreviewStrip books={books} />
    </MemoryRouter>);

    expect(markup.match(/aria-label="Open Book /g)).toHaveLength(COMPACT_BOOK_COVER_PREVIEW_SOURCE_LIMIT);
    expect(markup).toContain('href="/library/books/book-12"');
    expect(markup).not.toContain('href="/library/books/book-13"');
    expect(markup).toContain('aria-label="Book previews"');
  });
});
