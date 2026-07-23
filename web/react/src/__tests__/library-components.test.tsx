import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { CatalogTag, CompactBook, Page } from "@second-pass/spl-api";
import { BookRowComponent } from "../features/library/components/BookRowComponent";
import { BookListPageRegion } from "../features/library/regions/BookListPageRegion";
import { CatalogTagRailPageRegion, catalogTagSelection } from "../features/library/regions/CatalogTagRailPageRegion";

const book: CompactBook = {
  id: "book/id", title: "Visible Title", sortTitle: "Visible Title", subtitle: "HIDDEN SUBTITLE",
  authors: [{ id: "author", name: "Visible Author" }],
  series: { id: "series", name: "Visible Series", sortName: "Visible Series", seriesIndex: "3.00" },
  catalogTags: Array.from({ length: 8 }, (_, index) => ({ id: `tag-${index}`, name: `Tag ${index}`, slug: `tag-${index}` })),
  language: "HIDDEN LANGUAGE", publisher: "Visible Publisher", publishedYear: 1999, publishedMonth: 1, publishedDay: 2,
  publishedDatePrecision: "day", coverUrl: null, fileFormat: "HIDDEN FORMAT",
};

function renderList(page?: Page<CompactBook>, options: { loading?: boolean; error?: Error } = {}) {
  return renderToStaticMarkup(<MemoryRouter><BookListPageRegion
    page={page} pageNumber={1} pageSize={20} loading={options.loading ?? false} error={options.error}
    libraryPath="/library?q=visible" onPageChange={vi.fn()} onPageSizeChange={vi.fn()} onRetry={vi.fn()}
  /></MemoryRouter>);
}

describe("Library Books components", () => {
  it("renders only the accepted compact row presentation with canonical metadata icons", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><BookRowComponent book={book} libraryPath="/library?q=visible" /></MemoryRouter>);
    for (const value of ["Visible Title", "Visible Author", "Visible Series 3.00", "Visible Publisher", "Tag 0", "+2"]) expect(markup).toContain(value);
    for (const hidden of ["HIDDEN SUBTITLE", "1999", "HIDDEN LANGUAGE", "HIDDEN FORMAT", "Groups", "checksum", "identifier"]) expect(markup).not.toContain(hidden);
    for (const icon of ["person", "auto_stories", "apartment"]) expect(markup).toContain(`>${icon}</span>`);
    expect(markup).toContain("No cover available for Visible Title");
    expect(markup).toContain('href="/library/books/book%2Fid"');
  });

  it("renders loading, retryable error, empty, and standard pager states", () => {
    expect(renderList(undefined, { loading: true })).toContain("Loading books");
    expect(renderList(undefined, { error: new Error("Books unavailable") })).toContain("Retry");
    expect(renderList({ items: [], count: 0, next: null, previous: null })).toContain("No books match");
    const markup = renderList({ items: [book], count: 65, next: "next", previous: null });
    for (const size of [20, 30, 40, 50]) expect(markup).toContain(`<option value="${size}"`);
    expect(markup).not.toContain('<option value="100"');
    expect(markup).toContain("Showing 1-20 of 65");
  });

  it("renders viewer-scoped Catalog Tag counts, All tags, and independent failure", () => {
    const tags: CatalogTag[] = [{ id: "tag", name: "Fantasy", slug: "fantasy", bookCount: 12 }];
    const markup = renderToStaticMarkup(<CatalogTagRailPageRegion tags={tags} activeTag="fantasy" loading={false} onTagChange={vi.fn()} onRetry={vi.fn()} />);
    expect(markup).toContain("All tags");
    expect(markup).toContain("Fantasy");
    expect(markup).toContain(">12</span>");
    expect(markup).toContain('aria-pressed="true"');
    const failed = renderToStaticMarkup(<CatalogTagRailPageRegion loading={false} error={new Error("Tags unavailable")} onTagChange={vi.fn()} onRetry={vi.fn()} />);
    expect(failed).toContain("Tags unavailable");
    expect(failed).toContain("Retry tags");
    expect(catalogTagSelection("fantasy", "fantasy")).toBeUndefined();
    expect(catalogTagSelection("mystery", "fantasy")).toBe("fantasy");
  });
});
