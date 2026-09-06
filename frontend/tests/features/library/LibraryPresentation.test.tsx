import type { ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import type { CatalogTag, CompactBook, LibraryAuthor, LibrarySeries, Page, ShelfSummary } from "@second-pass/spl-api";
import { BookCoverEditor } from "../../../src/features/library/bookEdit/BookCoverEditor";
import { AuthorRow } from "../../../src/features/library/browse/AuthorRow";
import { CompactBookRow } from "../../../src/shared/books/CompactBookRow";
import { SeriesRow } from "../../../src/features/library/browse/SeriesRow";
import { readSelectedLibraryContextDisplay } from "../../../src/features/library/libraryPresentation";
import { libraryStateFromSearchParams } from "../../../src/features/library/libraryQuery";
import { AuthorListPageRegion } from "../../../src/features/library/browse/AuthorListPageRegion";
import { BookListPageRegion } from "../../../src/features/library/browse/BookListPageRegion";
import { retainTallestCatalogResultsHeight } from "../../../src/features/library/browse/CatalogBrowserPageRegion";
import { BookEditAuthorsSeriesPageRegion } from "../../../src/features/library/bookEdit/BookEditAuthorsSeriesPageRegion";
import { BookEditGroupsPageRegion } from "../../../src/features/library/bookEdit/BookEditGroupsPageRegion";
import { BookEditGroupShelvesPageRegion } from "../../../src/features/library/bookEdit/BookEditGroupShelvesPageRegion";
import { BookEditTabsPageRegion } from "../../../src/features/library/bookEdit/BookEditTabsPageRegion";
import { CatalogTagRailPageRegion, catalogTagSelection } from "../../../src/features/library/browse/CatalogTagRailPageRegion";
import { LibraryAxesPageRegion } from "../../../src/features/library/browse/LibraryAxesPageRegion";
import { LibraryAxisControlsPageRegion } from "../../../src/features/library/browse/LibraryAxisControlsPageRegion";
import { SeriesListPageRegion } from "../../../src/features/library/browse/SeriesListPageRegion";
import { SelectedLibraryContextPageRegion } from "../../../src/features/library/browse/SelectedLibraryContextPageRegion";

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
  it("keeps advanced Book group assignment controls immediate and protects sole Public", () => {
    const publicGroup = { id: "public", name: "Common Room", description: "Public", isPublicGroup: true };
    const simpleTabs = renderToStaticMarkup(<BookEditTabsPageRegion active="book" onChange={vi.fn()} />);
    const advancedTabs = renderToStaticMarkup(<BookEditTabsPageRegion active="groups" showGroups onChange={vi.fn()} />);
    expect(simpleTabs).toContain('role="tablist"');
    expect(simpleTabs).toContain('aria-controls="book-edit-book-panel"');
    expect(simpleTabs).not.toContain("Library Groups");
    expect(simpleTabs).toContain("Group Shelves");
    expect(advancedTabs).toContain("Library Groups");
    expect(advancedTabs).toContain("Group Shelves");

    const solePublic = renderToStaticMarkup(<MemoryRouter><BookEditGroupsPageRegion
      currentGroups={[publicGroup]}
      availableGroups={[publicGroup, { id: "custom", name: "Readers", description: "", isPublicGroup: false }]}
      loading={false}
      mutation={{ pending: false }}
      disabled={false}
      onRetry={vi.fn()}
      onSelectionChange={vi.fn()}
      onAdd={vi.fn()}
      onRemove={vi.fn()}
    /></MemoryRouter>);
    expect(solePublic).toContain("Common Room");
    expect(solePublic).toContain('href="/groups/public"');
    expect(solePublic).not.toContain("Remove Common Room");
    expect(solePublic).toContain("Readers");
    expect(solePublic).toContain('aria-label="Add group"');
  });

  it("keeps Book Edit Group Shelves constrained to linked group rows and authorized removal", () => {
    const shelf: ShelfSummary = {
      id: "shelf/id",
      name: "Editors' Picks",
      description: "Group picks",
      ownerType: "group",
      ownerUser: null,
      ownerGroup: { id: "group", name: "Editors", isPublicGroup: false },
      visibility: "private",
      itemCount: 3,
      matchedItemId: "item/id",
      canEdit: true,
    };
    const markup = renderToStaticMarkup(<MemoryRouter><BookEditGroupShelvesPageRegion
      shelves={[shelf, { ...shelf, id: "readonly", name: "Read only", matchedItemId: "readonly-item", canEdit: false }]}
      loading={false}
      mutation={{ pending: false }}
      disabled={false}
      shelfNavigationState={() => ({ contextual: true })}
      onRetry={vi.fn()}
      onRemove={vi.fn()}
    /></MemoryRouter>);

    expect(markup).toContain("Only group-owned shelves are shown here.");
    expect(markup).toContain('href="/shelves/shelf%2Fid"');
    expect(markup).toContain("Editors");
    expect(markup).toContain('aria-label="Remove Editors&#x27; Picks"');
    expect(markup).not.toContain('aria-label="Remove Read only"');
    expect(markup).not.toContain("Add to shelf");
    expect(markup).not.toContain("Edit Shelf");
  });

  it("keeps Book Edit cover mutation behind one bounded editor trigger", () => {
    const markup = renderToStaticMarkup(<BookCoverEditor
      coverUrl="/media/cover.jpg"
      title="Book"
      inputResetKey={0}
      state={{ pending: false }}
      onFileChange={vi.fn()}
      onReplace={vi.fn()}
      onClear={vi.fn()}
    />);
    expect(markup).toContain("Change Cover");
    expect(markup).not.toContain('type="file"');
    expect(markup).not.toContain("Clear Cover");
  });

  it("renders only the accepted compact row presentation", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><CompactBookRow book={book} detailPath="/library/books/book%2Fid" /></MemoryRouter>);
    for (const value of ["Visible Title", "Visible Author", "Visible Series 3.00", "Visible Publisher", "Tag 0", "+2"]) expect(markup).toContain(value);
    for (const hidden of ["HIDDEN SUBTITLE", "1999", "HIDDEN LANGUAGE", "HIDDEN FORMAT", "Groups", "checksum", "identifier"]) expect(markup).not.toContain(hidden);
    expect(markup).toContain("No cover available for Visible Title");
    expect(markup).toContain('href="/library/books/book%2Fid"');
  });

  it("keeps compact Book rows action-free by default and accepts caller-owned actions", () => {
    const readOnly = renderToStaticMarkup(<MemoryRouter><CompactBookRow book={book} detailPath="/library/books/book" /></MemoryRouter>);
    const actionable = renderToStaticMarkup(<MemoryRouter><CompactBookRow
      book={book}
      detailPath="/library/books/book"
      actions={<button type="button" aria-label="Add Visible Title">Add</button>}
    /></MemoryRouter>);

    expect(readOnly).not.toContain("Add Visible Title");
    expect(actionable).toContain('aria-label="Add Visible Title"');
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

  it("renders viewer-scoped Catalog Tag counts before their paired names", () => {
    const tags: CatalogTag[] = [
      { id: "tag-1", name: "Fantasy and Extremely Long Adventures", slug: "fantasy", bookCount: 12 },
      { id: "tag-2", name: "History", slug: "history", bookCount: 304 },
    ];
    const markup = renderToStaticMarkup(<CatalogTagRailPageRegion tags={tags} activeTag="fantasy" loading={false} onTagChange={vi.fn()} onRetry={vi.fn()} />);
    expect(markup).toContain("All tags");
    expect(markup).toContain("(12)");
    expect(markup).toContain("(304)");
    expect(markup).toContain('title="Fantasy and Extremely Long Adventures"');
    expect(markup).toContain('aria-pressed="true"');
    expect(markup).toContain('aria-current="true"');
    expect(markup).not.toMatch(/Add Catalog Tag|Edit Catalog Tag|Delete Catalog Tag|Merge Catalog Tags/);
    const failed = renderToStaticMarkup(<CatalogTagRailPageRegion loading={false} error={new Error("Tags unavailable")} onTagChange={vi.fn()} onRetry={vi.fn()} />);
    expect(failed).toContain("Tags unavailable");
    expect(failed).toContain("Retry tags");
    expect(catalogTagSelection("fantasy", "fantasy")).toBeUndefined();
    expect(catalogTagSelection("mystery", "fantasy")).toBe("fantasy");
  });

  it("keeps an active Catalog Tag visible when the contextual result set is empty", () => {
    const active = { id: "tag-1", name: "Fantasy", slug: "fantasy", bookCount: 12 };
    const markup = renderToStaticMarkup(<CatalogTagRailPageRegion
      tags={[]}
      activeTag="fantasy"
      activeTagDetails={active}
      loading={false}
      onTagChange={vi.fn()}
      onRetry={vi.fn()}
    />);

    expect(markup).toContain("Fantasy");
    expect(markup).toContain('aria-pressed="true"');
    expect(markup).not.toContain("(0)");
    expect(markup).not.toContain("(12)");
  });

  it("retains the tallest results height across Book pages", () => {
    expect(retainTallestCatalogResultsHeight(640, 390)).toBe(640);
    expect(retainTallestCatalogResultsHeight(640, 780)).toBe(780);
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
    const axisBar = axisRegion.props.children[1] as ReactElement<{ children: ReactElement[] }>;
    const nav = axisBar.props.children[0] as ReactElement<{ children: ReactElement<{ onClick: () => void }>[] }>;
    nav.props.children[1]!.props.onClick();
    expect(onViewChange).toHaveBeenCalledWith("authors");

    const activeAuthors = LibraryAxesPageRegion({ activeView: "authors", onViewChange }) as ReactElement<{ children: ReactElement[] }>;
    const activeAxisBar = activeAuthors.props.children[1] as ReactElement<{ children: ReactElement[] }>;
    const activeNav = activeAxisBar.props.children[0] as ReactElement<{ children: ReactElement<{ onClick: () => void }>[] }>;
    activeNav.props.children[1]!.props.onClick();
    expect(onViewChange).toHaveBeenLastCalledWith("authors");

    const managedAuthors = renderToStaticMarkup(<MemoryRouter><LibraryAxesPageRegion activeView="authors" canManageCatalog onViewChange={vi.fn()} /></MemoryRouter>);
    expect(managedAuthors).toContain('href="/library/authors/new"');
  });

  it("lets All tags clear the active tag on every Library axis", () => {
    expect(catalogTagSelection("fantasy", "fantasy")).toBeUndefined();
    const markup = renderToStaticMarkup(<CatalogTagRailPageRegion tags={[]} activeTag="fantasy" loading={false} onTagChange={vi.fn()} onRetry={vi.fn()} />);
    expect(markup).toMatch(/catalog-tag-rail__all" aria-pressed="false">All tags/);
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
    const authorMarkup = renderToStaticMarkup(<MemoryRouter><AuthorRow author={author} libraryPath="/library?view=authors" contextPath="/library?view=authors&author=author-1" /></MemoryRouter>);
    expect(authorMarkup).toContain("Visible Author");
    expect(authorMarkup).toContain("1 Book");
    expect(authorMarkup).not.toContain("HIDDEN BIOGRAPHY");
    expect(authorMarkup).toContain("No cover available for Preview Book");
    expect(authorMarkup).toContain('href="/library/books/book%2Fid"');
    expect(authorMarkup).toContain('href="/library?view=authors&amp;author=author-1"');
    expect(authorMarkup).toContain("library-axis-row-component compact-cover-preview-row");
    expect(authorMarkup).toContain("library-axis-row-component__identity compact-cover-preview-row__primary");

    const seriesMarkup = renderToStaticMarkup(<MemoryRouter><SeriesRow series={series} libraryPath="/library?view=series" contextPath="/library?view=series&series=series-1" /></MemoryRouter>);
    expect(seriesMarkup).toContain("Visible Series");
    expect(seriesMarkup).toContain("3 Books");
    expect(seriesMarkup).not.toContain("HIDDEN SUMMARY");
    expect(seriesMarkup).toContain('loading="lazy"');
    expect(seriesMarkup).toContain('href="/library/books/book-2"');
    expect(seriesMarkup).toContain('href="/library?view=series&amp;series=series-1"');
    expect((authorMarkup.match(/<a /g) ?? []).length).toBe(2);
    expect((seriesMarkup.match(/<a /g) ?? []).length).toBe(2);

    expect(authorMarkup).not.toContain('href="/library/authors/author-1/edit"');
    expect(seriesMarkup).not.toContain('href="/library/series/series-1/edit"');
    expect(authorMarkup).not.toContain("Delete");
    expect(seriesMarkup).not.toContain("Delete");
  });

  it("renders rich selected context detail without redundant back actions", () => {
    const biography = `<p>${"Visible biography ".repeat(20)}<strong>formatted</strong></p>`;
    const named = renderToStaticMarkup(<SelectedLibraryContextPageRegion kind="author" name="Visible Author" blurb={biography} bookCount={1} />);
    expect(named).toContain("Visible Author");
    expect(named).toContain("1 Book");
    expect(named).toContain("<strong>formatted</strong>");
    expect(named).not.toContain("&lt;p&gt;");
    expect(named).toContain("Show more");
    expect(named).not.toContain("Books by");
    expect(named).not.toContain("Back to Authors");
    const unavailable = renderToStaticMarkup(<SelectedLibraryContextPageRegion kind="series" name="Stale Series" unavailable />);
    expect(unavailable).toContain("Series unavailable");
    expect(unavailable).not.toContain("Stale Series");
    expect(unavailable).not.toContain("Back to Series");
    const editable = renderToStaticMarkup(<MemoryRouter><SelectedLibraryContextPageRegion kind="author" entityId="author-1" name="Visible Author" canEdit returnTo="/library?view=authors&author=author-1" /></MemoryRouter>);
    expect(editable).toContain('href="/library/authors/author-1/edit"');
    expect(named).not.toContain('href="/library/authors/author-1/edit"');

    const seriesDetail = renderToStaticMarkup(<SelectedLibraryContextPageRegion kind="series" name="Visible Series" blurb="<ul><li>First volume</li></ul>" bookCount={3} />);
    expect(seriesDetail).toContain("<ul><li>First volume</li></ul>");
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
        catalogTagNames: [], authorIds: [author.id], seriesId: series.id, seriesIndex: "1.25", identifiers: [],
      }}
      authors={[author]}
      series={[series]}
      authorsLoading={false}
      seriesLoading={false}
      breadcrumbTrail={[
        { label: "Library", to: "/library", icon: "library" },
        { label: "Books", to: "/library", icon: "book" },
        { label: "Book", to: "/library/books/book", icon: "book" },
        { label: "Edit" },
      ]}
      returnTo="/library/books/book/edit"
      onRetryAuthors={vi.fn()}
      onRetrySeries={vi.fn()}
      onChange={vi.fn()}
    /></MemoryRouter>);
    for (const path of [
      "/library/authors/new",
      "/library/series/new",
      "/library/series/series-1/edit",
    ]) expect(markup).toContain(`href="${path}"`);
    expect(markup).not.toContain('href="/library/authors/author-1/edit"');
    expect(markup).toContain('type="number"');
    expect(markup).toContain('min="0.01"');
    expect(markup).toContain('step="0.01"');
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
