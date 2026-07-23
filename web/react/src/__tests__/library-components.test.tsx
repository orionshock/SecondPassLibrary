import type { ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { CatalogTag, CompactBook, LibraryAuthor, LibrarySeries, Page } from "@second-pass/spl-api";
import { AuthorRowComponent } from "../features/library/components/AuthorRowComponent";
import { BookRowComponent } from "../features/library/components/BookRowComponent";
import { SeriesRowComponent } from "../features/library/components/SeriesRowComponent";
import { AuthorListPageRegion } from "../features/library/regions/AuthorListPageRegion";
import { BookListPageRegion } from "../features/library/regions/BookListPageRegion";
import { CatalogTagRailPageRegion, catalogTagSelection } from "../features/library/regions/CatalogTagRailPageRegion";
import { LibraryAxesPageRegion } from "../features/library/regions/LibraryAxesPageRegion";
import { LibraryAxisControlsPageRegion } from "../features/library/regions/LibraryAxisControlsPageRegion";
import { SeriesListPageRegion } from "../features/library/regions/SeriesListPageRegion";

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
    const tags: CatalogTag[] = [{ id: "tag", name: "Fantasy and Extremely Long Adventures", slug: "fantasy", bookCount: 12 }];
    const markup = renderToStaticMarkup(<CatalogTagRailPageRegion tags={tags} activeTag="fantasy" loading={false} onTagChange={vi.fn()} onRetry={vi.fn()} />);
    expect(markup).toContain("All tags");
    expect(markup).toContain("Fantasy and Extremely Long Adventures");
    expect(markup).toContain('class="catalog-tag-rail__name" title="Fantasy and Extremely Long Adventures"');
    expect(markup).toContain(">12</span>");
    expect(markup).toContain('aria-pressed="true"');
    const failed = renderToStaticMarkup(<CatalogTagRailPageRegion loading={false} error={new Error("Tags unavailable")} onTagChange={vi.fn()} onRetry={vi.fn()} />);
    expect(failed).toContain("Tags unavailable");
    expect(failed).toContain("Retry tags");
    expect(catalogTagSelection("fantasy", "fantasy")).toBeUndefined();
    expect(catalogTagSelection("mystery", "fantasy")).toBe("fantasy");
  });

  it("keeps all real axis controls and context-sensitive controls in the stable shell", () => {
    const onViewChange = vi.fn();
    const axes = renderToStaticMarkup(<LibraryAxesPageRegion activeView="authors" onViewChange={onViewChange} />);
    for (const label of ["Library", "Books", "Authors", "Series"]) expect(axes).toContain(label);
    expect(axes).toMatch(/aria-current="page"[^>]*>Authors/);
    const controls = renderToStaticMarkup(<LibraryAxisControlsPageRegion view="series" search="" ordering="name" onSearchChange={vi.fn()} onSearch={vi.fn()} onOrderingChange={vi.fn()} />);
    expect(controls).toContain('placeholder="Series name..."');
    expect(controls).toContain("Name A-Z");
    const inactiveTags = renderToStaticMarkup(<CatalogTagRailPageRegion enabled={false} loading={false} onTagChange={vi.fn()} onRetry={vi.fn()} />);
    expect(inactiveTags).toContain("Catalog Tags");
    expect(inactiveTags).toContain("Available when browsing Books.");
    expect(inactiveTags).not.toContain("All tags");

    const axisRegion = LibraryAxesPageRegion({ activeView: "books", onViewChange }) as ReactElement<{ children: ReactElement[] }>;
    const nav = axisRegion.props.children[1] as ReactElement<{ children: ReactElement<{ onClick: () => void }>[] }>;
    nav.props.children[1]!.props.onClick();
    expect(onViewChange).toHaveBeenCalledWith("authors");
  });
});

describe("Library Author and Series components", () => {
  const author: LibraryAuthor = {
    id: "author-1", name: "Visible Author", sortName: "Author, Visible", biography: "HIDDEN BIOGRAPHY", bookCount: 1,
    previewBooks: [{ id: "book/id", title: "Preview Book", coverUrl: null }],
  };
  const series: LibrarySeries = {
    id: "series-1", name: "Visible Series", sortName: "Visible Series", summary: "HIDDEN SUMMARY", bookCount: 3,
    previewBooks: [{ id: "book-2", title: "Covered Book", coverUrl: "/cover.jpg" }],
  };

  it("renders compact rows, pluralized counts, bounded previews, fallbacks, and placeholder links", () => {
    const authorMarkup = renderToStaticMarkup(<MemoryRouter><AuthorRowComponent author={author} libraryPath="/library?view=authors" /></MemoryRouter>);
    expect(authorMarkup).toContain("Visible Author");
    expect(authorMarkup).toContain("1 Book");
    expect(authorMarkup).not.toContain("HIDDEN BIOGRAPHY");
    expect(authorMarkup).toContain("No cover available for Preview Book");
    expect(authorMarkup).toContain('href="/library/books/book%2Fid"');

    const seriesMarkup = renderToStaticMarkup(<MemoryRouter><SeriesRowComponent series={series} libraryPath="/library?view=series" /></MemoryRouter>);
    expect(seriesMarkup).toContain("Visible Series");
    expect(seriesMarkup).toContain("3 Books");
    expect(seriesMarkup).not.toContain("HIDDEN SUMMARY");
    expect(seriesMarkup).toContain('loading="lazy"');
    expect(seriesMarkup).toContain('href="/library/books/book-2"');
  });

  it("renders axis loading, retryable error, search-aware empty, and standard pagers", () => {
    const common = { pageNumber: 1, pageSize: 20, libraryPath: "/library", onPageChange: vi.fn(), onPageSizeChange: vi.fn(), onRetry: vi.fn() };
    const authorLoading = renderToStaticMarkup(<MemoryRouter><AuthorListPageRegion loading={true} searching={false} {...common} /></MemoryRouter>);
    const authorError = renderToStaticMarkup(<MemoryRouter><AuthorListPageRegion loading={false} error={new Error("Authors unavailable")} searching={false} {...common} /></MemoryRouter>);
    const authorEmpty = renderToStaticMarkup(<MemoryRouter><AuthorListPageRegion page={{ items: [], count: 0, next: null, previous: null }} loading={false} searching={true} {...common} /></MemoryRouter>);
    expect(authorLoading).toContain("Loading authors");
    expect(authorError).toContain("Authors unavailable");
    expect(authorEmpty).toContain("No authors match this search.");

    const seriesMarkup = renderToStaticMarkup(<MemoryRouter><SeriesListPageRegion page={{ items: [series], count: 51, next: "next", previous: null }} loading={false} searching={false} {...common} /></MemoryRouter>);
    for (const size of [20, 30, 40, 50]) expect(seriesMarkup).toContain(`<option value="${size}"`);
    expect(seriesMarkup).toContain("Showing 1-20 of 51");
    const seriesError = renderToStaticMarkup(<MemoryRouter><SeriesListPageRegion loading={false} error={new Error("Series unavailable")} searching={false} {...common} /></MemoryRouter>);
    const seriesEmpty = renderToStaticMarkup(<MemoryRouter><SeriesListPageRegion page={{ items: [], count: 0, next: null, previous: null }} loading={false} searching={true} {...common} /></MemoryRouter>);
    expect(seriesError).toContain("Series unavailable");
    expect(seriesEmpty).toContain("No series match this search.");
  });
});
