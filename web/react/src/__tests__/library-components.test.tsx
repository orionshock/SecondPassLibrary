import type { ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { CatalogTag, CompactBook, LibraryAuthor, LibrarySeries, Page } from "@second-pass/spl-api";
import { BookCoverEditorComponent } from "../features/library/components/BookCoverEditorComponent";
import { AuthorRowComponent } from "../features/library/components/AuthorRowComponent";
import { BookRowComponent } from "../features/library/components/BookRowComponent";
import { SeriesRowComponent } from "../features/library/components/SeriesRowComponent";
import { readSelectedLibraryContextDisplay } from "../features/library/libraryPresentation";
import { confirmBookCoverClear } from "../features/library/bookCoverMutation";
import { libraryStateFromSearchParams } from "../features/library/libraryQuery";
import { AuthorListPageRegion } from "../features/library/regions/AuthorListPageRegion";
import { BookListPageRegion } from "../features/library/regions/BookListPageRegion";
import { BookEditAuthorsSeriesPageRegion } from "../features/library/regions/BookEditAuthorsSeriesPageRegion";
import { CatalogTagRailPageRegion, catalogTagSelection } from "../features/library/regions/CatalogTagRailPageRegion";
import { LibraryAxesPageRegion } from "../features/library/regions/LibraryAxesPageRegion";
import { LibraryAxisControlsPageRegion } from "../features/library/regions/LibraryAxisControlsPageRegion";
import { SeriesListPageRegion } from "../features/library/regions/SeriesListPageRegion";
import { SelectedLibraryContextPageRegion } from "../features/library/regions/SelectedLibraryContextPageRegion";

const book: CompactBook = {
  id: "book/id", title: "Visible Title", sortTitle: "Visible Title", subtitle: "HIDDEN SUBTITLE",
  authors: [{ id: "author", name: "Visible Author" }],
  series: { id: "series", name: "Visible Series", sortName: "Visible Series", seriesIndex: "3.00" },
  catalogTags: Array.from({ length: 8 }, (_, index) => ({ id: `tag-${index}`, name: `Tag ${index}`, slug: `tag-${index}` })),
  language: "HIDDEN LANGUAGE", publisher: "Visible Publisher", publishedYear: 1999, publishedMonth: 1, publishedDay: 2,
  publishedDatePrecision: "day", coverUrl: null, fileFormat: "HIDDEN FORMAT",
};

function renderList(page?: Page<CompactBook>, options: { loading?: boolean; error?: Error; searching?: boolean; tagged?: boolean } = {}) {
  return renderToStaticMarkup(<MemoryRouter><BookListPageRegion
    page={page} pageNumber={1} pageSize={20} loading={options.loading ?? false} error={options.error}
    searching={options.searching} tagged={options.tagged}
    libraryPath="/library?q=visible" onPageChange={vi.fn()} onPageSizeChange={vi.fn()} onRetry={vi.fn()}
  /></MemoryRouter>);
}

describe("Library Books components", () => {
  it("keeps Book Edit cover controls server-blind and explicitly confirms clear", () => {
    const withoutSelection = renderToStaticMarkup(<BookCoverEditorComponent
      coverUrl="/media/cover.jpg"
      inputResetKey={0}
      state={{ pending: false }}
      onFileChange={vi.fn()}
      onReplace={vi.fn()}
      onClear={vi.fn()}
    />);
    expect(withoutSelection).toContain('accept="image/jpeg,image/png,image/webp"');
    expect(withoutSelection).toMatch(/<button[^>]*type="button"[^>]*disabled=""[^>]*>Replace cover/);
    expect(withoutSelection).toContain(">Clear cover</button>");

    const noCover = renderToStaticMarkup(<BookCoverEditorComponent
      coverUrl={null}
      selectedFile={new File(["cover"], "cover.jpg")}
      inputResetKey={0}
      state={{ pending: false }}
      onFileChange={vi.fn()}
      onReplace={vi.fn()}
      onClear={vi.fn()}
    />);
    expect(noCover).not.toContain(">Clear cover</button>");
    expect(noCover).not.toMatch(/>Replace cover<\/button>.*disabled/);

    const confirm = vi.fn(() => true);
    expect(confirmBookCoverClear(confirm)).toBe(true);
    expect(confirm).toHaveBeenCalledOnce();
  });

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
    const emptyPage = { items: [], count: 0, next: null, previous: null };
    expect(renderList(emptyPage)).toContain("No books.");
    expect(renderList(emptyPage, { searching: true })).toContain("No books match this search.");
    expect(renderList(emptyPage, { tagged: true })).toContain("No books for this Catalog Tag.");
    expect(renderList(emptyPage, { searching: true, tagged: true })).toContain("No books match this search within this Catalog Tag.");
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
    const activeTags = renderToStaticMarkup(<CatalogTagRailPageRegion tags={[{ id: "tag", name: "Fantasy", slug: "fantasy", bookCount: 4 }]} activeTag="fantasy" loading={false} onTagChange={vi.fn()} onRetry={vi.fn()} />);
    expect(activeTags).toContain("All tags");
    expect(activeTags).toContain('aria-pressed="true"');

    const axisRegion = LibraryAxesPageRegion({ activeView: "books", onViewChange }) as ReactElement<{ children: ReactElement[] }>;
    const nav = axisRegion.props.children[1] as ReactElement<{ children: ReactElement<{ onClick: () => void }>[] }>;
    nav.props.children[1]!.props.onClick();
    expect(onViewChange).toHaveBeenCalledWith("authors");
  });

  it("lets All tags clear the active tag on every Library axis", () => {
    const onTagChange = vi.fn();
    const rail = CatalogTagRailPageRegion({ tags: [], activeTag: "fantasy", loading: false, onTagChange, onRetry: vi.fn() }) as ReactElement<{ children: ReactElement[] }>;
    const desktop = rail.props.children[1] as ReactElement<{ children: ReactElement<{ children: ReactElement[] }> }>;
    const allTags = desktop.props.children.props.children[0] as ReactElement<{ onClick: () => void }>;
    allTags.props.onClick();
    expect(onTagChange).toHaveBeenCalledWith(undefined);
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
    const authorMarkup = renderToStaticMarkup(<MemoryRouter><AuthorRowComponent author={author} libraryPath="/library?view=authors" contextPath="/library?view=authors&author=author-1" /></MemoryRouter>);
    expect(authorMarkup).toContain("Visible Author");
    expect(authorMarkup).toContain("1 Book");
    expect(authorMarkup).not.toContain("HIDDEN BIOGRAPHY");
    expect(authorMarkup).toContain("No cover available for Preview Book");
    expect(authorMarkup).toContain('href="/library/books/book%2Fid"');
    expect(authorMarkup).toContain('href="/library?view=authors&amp;author=author-1"');

    const seriesMarkup = renderToStaticMarkup(<MemoryRouter><SeriesRowComponent series={series} libraryPath="/library?view=series" contextPath="/library?view=series&series=series-1" /></MemoryRouter>);
    expect(seriesMarkup).toContain("Visible Series");
    expect(seriesMarkup).toContain("3 Books");
    expect(seriesMarkup).not.toContain("HIDDEN SUMMARY");
    expect(seriesMarkup).toContain('loading="lazy"');
    expect(seriesMarkup).toContain('href="/library/books/book-2"');
    expect(seriesMarkup).toContain('href="/library?view=series&amp;series=series-1"');
    expect((authorMarkup.match(/<a /g) ?? []).length).toBe(2);
    expect((seriesMarkup.match(/<a /g) ?? []).length).toBe(2);

    const editableAuthor = renderToStaticMarkup(<MemoryRouter><AuthorRowComponent author={author} libraryPath="/library?view=authors" contextPath="/library?view=authors&author=author-1" canEdit /></MemoryRouter>);
    const editableSeries = renderToStaticMarkup(<MemoryRouter><SeriesRowComponent series={series} libraryPath="/library?view=series" contextPath="/library?view=series&series=series-1" canEdit /></MemoryRouter>);
    expect(editableAuthor).toContain('href="/library/authors/author-1/edit"');
    expect(editableSeries).toContain('href="/library/series/series-1/edit"');
    expect(editableAuthor).not.toContain("Delete");
    expect(editableSeries).not.toContain("Delete");
  });

  it("renders named and direct-load selected context headers with bounded back actions", () => {
    const named = renderToStaticMarkup(<SelectedLibraryContextPageRegion kind="author" name="Visible Author" bookCount={1} onBack={vi.fn()} />);
    expect(named).toContain("Books by Visible Author");
    expect(named).toContain("1 Book");
    expect(named).toContain("Back to Authors");
    const direct = renderToStaticMarkup(<SelectedLibraryContextPageRegion kind="series" onBack={vi.fn()} />);
    expect(direct).toContain("Series Books");
    expect(direct).toContain("Back to Series");
    const editable = renderToStaticMarkup(<MemoryRouter><SelectedLibraryContextPageRegion kind="author" entityId="author-1" name="Visible Author" canEdit returnTo="/library?view=authors&author=author-1" onBack={vi.fn()} /></MemoryRouter>);
    expect(editable).toContain('href="/library/authors/author-1/edit"');
  });

  it("uses Book controls and selected-context sort choices", () => {
    const authorControls = renderToStaticMarkup(<LibraryAxisControlsPageRegion view="authors" selectedContext="author" search="" ordering="title" onSearchChange={vi.fn()} onSearch={vi.fn()} onOrderingChange={vi.fn()} />);
    expect(authorControls).toContain('placeholder="Book title..."');
    expect(authorControls).toContain("Title A-Z");
    const seriesControls = renderToStaticMarkup(<LibraryAxisControlsPageRegion view="series" selectedContext="series" search="" ordering="series_index" onSearchChange={vi.fn()} onSearch={vi.fn()} onOrderingChange={vi.fn()} />);
    expect(seriesControls).toContain("Series Order");
  });

  it("links Book Edit relationship management to lifecycle routes without inline forms", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><BookEditAuthorsSeriesPageRegion
      draft={{
        title: "Book", sortTitle: "", subtitle: "", description: "", publisher: "", language: "",
        publishedDatePrecision: "", publishedYear: "", publishedMonth: "", publishedDay: "",
        catalogTagNames: [], authorIds: [author.id], seriesId: series.id, seriesIndex: "1.0", identifiers: [],
      }}
      authors={[author]}
      series={[series]}
      authorsLoading={false}
      seriesLoading={false}
      returnTo="/library/books/book/edit"
      onRetryAuthors={vi.fn()}
      onRetrySeries={vi.fn()}
      onChange={vi.fn()}
    /></MemoryRouter>);
    for (const path of [
      "/library/authors/new",
      "/library/authors/author-1/edit",
      "/library/series/new",
      "/library/series/series-1/edit",
    ]) expect(markup).toContain(`href="${path}"`);
  });

  it("keeps selected-context empty copy anti-leakage-safe and accepts matching navigation display state", () => {
    const empty = renderToStaticMarkup(<MemoryRouter><BookListPageRegion
      page={{ items: [], count: 0, next: null, previous: null }} pageNumber={1} pageSize={20} loading={false}
      searching={false} tagged={false} selectedContext={{ kind: "author", label: "Author Books" }} libraryPath="/library"
      onPageChange={vi.fn()} onPageSizeChange={vi.fn()} onRetry={vi.fn()}
    /></MemoryRouter>);
    expect(empty).toContain("No books found for this author.");
    expect(empty).not.toContain("does not exist");

    const id = "11111111-1111-4111-8111-111111111111";
    const query = libraryStateFromSearchParams(new URLSearchParams(`view=authors&author=${id}`));
    expect(readSelectedLibraryContextDisplay({ librarySelectedContext: { kind: "author", id, name: "Visible Author", bookCount: 2 } }, query)).toEqual({ kind: "author", id, name: "Visible Author", bookCount: 2 });
    expect(readSelectedLibraryContextDisplay({ librarySelectedContext: { kind: "author", id: "other", name: "Hidden" } }, query)).toBeUndefined();
  });

  it("renders axis loading, retryable error, search-aware empty, and standard pagers", () => {
    const common = { pageNumber: 1, pageSize: 20, libraryPath: "/library", contextPathFor: () => "/library", tagged: false, onPageChange: vi.fn(), onPageSizeChange: vi.fn(), onRetry: vi.fn() };
    const authorLoading = renderToStaticMarkup(<MemoryRouter><AuthorListPageRegion loading={true} searching={false} {...common} /></MemoryRouter>);
    const authorError = renderToStaticMarkup(<MemoryRouter><AuthorListPageRegion loading={false} error={new Error("Authors unavailable")} searching={false} {...common} /></MemoryRouter>);
    const authorEmpty = renderToStaticMarkup(<MemoryRouter><AuthorListPageRegion page={{ items: [], count: 0, next: null, previous: null }} loading={false} searching={true} {...common} /></MemoryRouter>);
    expect(authorLoading).toContain("Loading authors");
    expect(authorError).toContain("Authors unavailable");
    expect(authorEmpty).toContain("No authors match this search.");
    const taggedAuthorEmpty = renderToStaticMarkup(<MemoryRouter><AuthorListPageRegion page={{ items: [], count: 0, next: null, previous: null }} loading={false} searching={false} {...common} tagged /></MemoryRouter>);
    const searchedTaggedAuthorEmpty = renderToStaticMarkup(<MemoryRouter><AuthorListPageRegion page={{ items: [], count: 0, next: null, previous: null }} loading={false} searching {...common} tagged /></MemoryRouter>);
    expect(taggedAuthorEmpty).toContain("No authors for this Catalog Tag.");
    expect(searchedTaggedAuthorEmpty).toContain("No authors match this search within this Catalog Tag.");

    const seriesMarkup = renderToStaticMarkup(<MemoryRouter><SeriesListPageRegion page={{ items: [series], count: 51, next: "next", previous: null }} loading={false} searching={false} {...common} /></MemoryRouter>);
    for (const size of [20, 30, 40, 50]) expect(seriesMarkup).toContain(`<option value="${size}"`);
    expect(seriesMarkup).toContain("Showing 1-20 of 51");
    const seriesError = renderToStaticMarkup(<MemoryRouter><SeriesListPageRegion loading={false} error={new Error("Series unavailable")} searching={false} {...common} /></MemoryRouter>);
    const seriesEmpty = renderToStaticMarkup(<MemoryRouter><SeriesListPageRegion page={{ items: [], count: 0, next: null, previous: null }} loading={false} searching={true} {...common} /></MemoryRouter>);
    expect(seriesError).toContain("Series unavailable");
    expect(seriesEmpty).toContain("No series match this search.");
    const taggedSeriesEmpty = renderToStaticMarkup(<MemoryRouter><SeriesListPageRegion page={{ items: [], count: 0, next: null, previous: null }} loading={false} searching={false} {...common} tagged /></MemoryRouter>);
    const searchedTaggedSeriesEmpty = renderToStaticMarkup(<MemoryRouter><SeriesListPageRegion page={{ items: [], count: 0, next: null, previous: null }} loading={false} searching {...common} tagged /></MemoryRouter>);
    expect(taggedSeriesEmpty).toContain("No series for this Catalog Tag.");
    expect(searchedTaggedSeriesEmpty).toContain("No series match this search within this Catalog Tag.");

    const failedTags = renderToStaticMarkup(<CatalogTagRailPageRegion loading={false} error={new Error("Tags unavailable")} onTagChange={vi.fn()} onRetry={vi.fn()} />);
    expect(failedTags).toContain("Tags unavailable");
    expect(authorLoading).toContain("Loading authors");
  });
});
