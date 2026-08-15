import type { ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import type { BookDetail, LibraryGroup, ShelfSummary } from "@second-pass/spl-api";
import { breadcrumbLinkState, resolveBreadcrumbTrail } from "../../../../src/app/navigation/breadcrumbs";
import {
  bookBrowseDetailBreadcrumbs,
  bookDetailBreadcrumbFallback,
  bookEditBreadcrumbTrail,
  bookEditRelatedBreadcrumbTrail,
  bookGroupBreadcrumbTrail,
  bookGroupPreviewBreadcrumbTrail,
  bookIdentifierLabel,
  bookSeriesDisplay,
  bookShelfBreadcrumbTrail,
  bookShelfPreviewBreadcrumbTrail,
  formatBookFileSize,
  formatBookPublishedDate,
} from "../../../../src/features/library/bookDetailPresentation";
import { BookDetailHeroPageRegion } from "../../../../src/features/library/bookDetail/BookDetailHeroPageRegion";
import { BookDetailSectionsPageRegion } from "../../../../src/features/library/bookDetail/BookDetailSectionsPageRegion";
import { bookDetailQueryFromSearchParams, bookDetailSearchParams } from "../../../../src/features/library/bookTabs";

const book: BookDetail = {
  id: "11111111-1111-4111-8111-111111111111",
  title: "Battle Ground",
  sortTitle: "Battle Ground",
  subtitle: "A Novel of the Dresden Files",
  authors: [{ id: "22222222-2222-4222-8222-222222222222", name: "Jim Butcher" }],
  series: { id: "33333333-3333-4333-8333-333333333333", name: "Dresden Files", sortName: "Dresden Files", seriesIndex: "18.00" },
  language: "eng",
  publisher: "Penguin",
  publishedYear: 2020,
  publishedMonth: 7,
  publishedDay: 14,
  publishedDatePrecision: "day",
  coverUrl: null,
  description: "<p>hello</p>\nSecond line",
  identifiers: [{ id: "identifier", scheme: "isbn_13", value: "9781234567890" }],
  catalogTags: [{ id: "tag", name: "Fantasy", slug: "fantasy" }],
  file: { format: "epub", fileSize: 1536, checksum: "DO-NOT-RENDER", downloadUrl: "/download/book.epub" },
  groups: [
    { id: "group", name: "Common Room", description: "Everyone reads here", isPublicGroup: true },
    { id: "editors", name: "Editors", description: "Selected readers", isPublicGroup: false },
  ],
};

const shelves: ShelfSummary[] = [
  {
    id: "personal-shelf", name: "Current Favorites", description: "Reader picks", ownerType: "user",
    ownerUser: { profileId: "reader-profile", username: "reader" }, ownerGroup: null,
    visibility: "listed", itemCount: 12, matchedItemId: "item", canEdit: true,
    previewBooks: [{ id: "preview", title: "Preview Book", coverUrl: "/cover.jpg" }],
  },
  {
    id: "public-shelf", name: "Sci-Fi Stack", description: "", ownerType: "group",
    ownerUser: null, ownerGroup: { id: "public", name: "Common Room", isPublicGroup: true },
    visibility: "private", itemCount: 10, matchedItemId: null, canEdit: false,
  },
];

const groups: LibraryGroup[] = [
  {
    id: "group", name: "Common Room", description: "Everyone reads here", isPublicGroup: true,
    previewBooks: [{ id: "preview", title: "Preview Book", coverUrl: "/cover.jpg" }],
  },
  { id: "editors", name: "Editors", description: "Selected readers", isPublicGroup: false, previewBooks: [] },
];

function render(element: ReactElement): string {
  return renderToStaticMarkup(<MemoryRouter>{element}</MemoryRouter>);
}

describe("Book Detail presentation", () => {
  it("formats precise dates, file sizes, series, and identifier labels", () => {
    expect(formatBookPublishedDate(book)).toBe("2020-07-14");
    expect(formatBookPublishedDate({ ...book, publishedDatePrecision: "month" })).toBe("2020-07");
    expect(formatBookPublishedDate({ ...book, publishedDatePrecision: "year" })).toBe("2020");
    expect(formatBookPublishedDate({ ...book, publishedYear: null })).toBeUndefined();
    expect(formatBookFileSize(1536)).toBe("1.5 KB");
    expect(formatBookFileSize(null)).toBeUndefined();
    expect(bookSeriesDisplay(book.series!)).toBe("Dresden Files #18.00");
    expect(bookIdentifierLabel("isbn_13")).toBe("ISBN-13");
  });

  it("escapes description text and builds contextual entity and download links", () => {
    const markup = render(<BookDetailHeroPageRegion book={book} />);
    expect(markup).toContain("&lt;p&gt;hello&lt;/p&gt;");
    expect(markup).not.toContain("<p>hello</p>");
    expect(markup).toContain('href="/library?view=authors&amp;author=22222222-2222-4222-8222-222222222222"');
    expect(markup).toContain('href="/library?view=series&amp;series=33333333-3333-4333-8333-333333333333"');
    expect(markup).toContain('href="/download/book.epub"');
  });

  it("uses mapped file and identifier data in the Metadata section", () => {
    const metadata = render(<BookDetailSectionsPageRegion book={book} advancedGroupsEnabled={false} activeSection="metadata" onSectionChange={() => undefined} />);
    expect(metadata).toContain("DO-NOT-RENDER");
    expect(metadata).toContain("9781234567890");
    expect(metadata).toContain('role="tabpanel"');
  });

  it("uses the server-provided advanced-groups mode to gate visible groups", () => {
    const simple = render(<BookDetailSectionsPageRegion book={book} advancedGroupsEnabled={false} activeSection="shelves" onSectionChange={() => undefined} />);
    const advanced = render(<BookDetailSectionsPageRegion book={book} advancedGroupsEnabled activeSection="groups" groupsState={{ status: "ready", groups }} onSectionChange={() => undefined} />);
    expect(simple).not.toContain('id="book-detail-groups-tab"');
    expect(simple).not.toContain("Common Room");
    expect(advanced).toContain("Common Room");
    expect(advanced).toContain("Editors");
    expect(advanced).toContain('href="/groups/group"');
    expect(advanced).toContain('href="/groups/editors"');
    expect(advanced).toContain("group-row-component");
    expect(advanced).toContain("Everyone reads here");
    expect(advanced).toContain('aria-label="Open Preview Book"');
    expect(advanced).not.toContain("Manage");
  });

  it("links read-only server-scoped shelf facts without exposing mutations", () => {
    const markup = render(<BookDetailSectionsPageRegion
      book={book}
      advancedGroupsEnabled
      activeSection="shelves"
      shelvesState={{ status: "ready", shelves }}
      onSectionChange={() => undefined}
    />);
    expect(markup).toContain("Current Favorites");
    expect(markup).toContain("Reader picks");
    expect(markup).toContain('aria-label="User reader"');
    expect(markup).not.toContain("@reader");
    expect(markup).toContain('aria-label="Open Preview Book"');
    expect(markup).toContain("Sci-Fi Stack");
    expect(markup).toContain("Common Room");
    expect(markup).toContain('href="/shelves/personal-shelf"');
    expect(markup).toContain('href="/shelves/public-shelf"');
    expect(markup).not.toContain("Remove");
    expect(markup).not.toContain("Edit Shelf");
  });

  it("keeps Book Detail sections canonical and direct-linkable", () => {
    expect(bookDetailQueryFromSearchParams(new URLSearchParams(), true)).toEqual({ tab: "shelves", query: "" });
    expect(bookDetailQueryFromSearchParams(new URLSearchParams("trail=context&tab=metadata"), true)).toEqual({
      tab: "metadata", query: "trail=context&tab=metadata",
    });
    expect(bookDetailQueryFromSearchParams(new URLSearchParams("tab=unknown"), true)).toEqual({ tab: "shelves", query: "" });
    expect(bookDetailQueryFromSearchParams(new URLSearchParams("tab=groups"), false)).toEqual({ tab: "shelves", query: "" });
    expect(bookDetailSearchParams(new URLSearchParams("trail=context&tab=metadata"), "shelves").toString()).toBe("trail=context");
  });

  it("uses a null file projection to show repair state and suppress download", () => {
    const repairBook = { ...book, file: null };
    const hero = render(<BookDetailHeroPageRegion book={repairBook} />);
    expect(hero).toContain("This book’s EPUB file is unavailable.");
    expect(hero).not.toContain("Download EPUB");
  });

  it("exposes Book Edit only when the orchestrator grants Librarian-level access", () => {
    expect(render(<BookDetailHeroPageRegion book={book} />)).not.toContain("/edit");
    expect(render(<BookDetailHeroPageRegion book={book} canEdit editNavigationState={{ safe: true }} />)).toContain(`/library/books/${book.id}/edit`);
  });

  it("shows a configured Reader launcher only for an available EPUB", () => {
    const configured = render(<BookDetailHeroPageRegion book={book} readingClientBookUrl={`https://reader.example.com/#/reader/${book.id}`} />);
    expect(configured).toContain("Open in Reader");
    expect(configured).toContain(`href="https://reader.example.com/#/reader/${book.id}"`);
    expect(configured).toContain('target="_blank"');
    expect(configured).toContain('rel="noopener noreferrer"');
    expect(render(<BookDetailHeroPageRegion book={book} />)).not.toContain("Open in Reader");
    expect(render(<BookDetailHeroPageRegion book={{ ...book, file: null }} />)).not.toContain("Open in Reader");
  });
});

describe("Book Detail navigation", () => {
  it("builds direct, Books, selected Author, and selected Series breadcrumb trails", () => {
    expect(bookDetailBreadcrumbFallback("Battle Ground").map(({ label }) => label)).toEqual(["Library", "Books", "Battle Ground"]);
    expect(bookBrowseDetailBreadcrumbs({ title: "Battle Ground", libraryPath: "/library?q=battle" })).toEqual([
      { label: "Library", to: "/library", resetTrail: true, icon: "library" },
      { label: "Books", to: "/library?q=battle", resetTrail: true, icon: "book" },
      { label: "Battle Ground", icon: "book" },
    ]);
    expect(bookBrowseDetailBreadcrumbs({ title: "Battle Ground", libraryPath: "/library?view=authors&author=id", contextLabel: "Jim Butcher", contextKind: "author", parentLibraryPath: "/library?view=authors" })[1]?.icon).toBe("author");
    expect(bookBrowseDetailBreadcrumbs({ title: "Battle Ground", libraryPath: "/library?view=series&series=id", contextLabel: "Dresden Files", contextKind: "series", parentLibraryPath: "/library?view=series" })[1]?.icon).toBe("series");
    expect(bookEditBreadcrumbTrail(bookDetailBreadcrumbFallback("Old title"), book.id, "New title")).toEqual([
      { label: "Library", to: "/library", resetTrail: true, icon: "library" }, { label: "Books", to: "/library", resetTrail: true, icon: "book" },
      { label: "New title", to: `/library/books/${book.id}`, icon: "book" }, { label: "Edit" },
    ]);
  });

  it("preserves selected browse context when following the Book ancestor from Edit", () => {
    const editTrail = bookEditBreadcrumbTrail(
      bookBrowseDetailBreadcrumbs({
        title: "Storm Front",
        libraryPath: "/library?view=series&series=series-id",
        contextLabel: "Dresden Files",
        contextKind: "series",
        parentLibraryPath: "/library?view=series",
      }),
      book.id,
      "Storm Front",
    );
    expect(resolveBreadcrumbTrail(breadcrumbLinkState(editTrail, editTrail.length - 2), [])).toEqual([
      { label: "Library", to: "/library?view=series", icon: "library" },
      { label: "Dresden Files", to: "/library?view=series&series=series-id", icon: "series" },
      { label: "Storm Front", to: `/library/books/${book.id}`, icon: "book" },
    ]);
  });

  it("extends the validated Book trail when navigating to a containing Shelf", () => {
    expect(bookShelfBreadcrumbTrail(
      bookBrowseDetailBreadcrumbs({
        title: "Storm Front",
        libraryPath: "/library?view=series&series=series-id",
        contextLabel: "Dresden Files",
        contextKind: "series",
        parentLibraryPath: "/library?view=series",
      }),
      book.id,
      "Storm Front",
      "Favorites",
    )).toEqual([
      { label: "Library", to: "/library?view=series", resetTrail: true, icon: "library" },
      { label: "Dresden Files", to: "/library?view=series&series=series-id", icon: "series" },
      { label: "Storm Front", to: `/library/books/${book.id}`, icon: "book" },
      { label: "Favorites", icon: "shelf" },
    ]);
  });

  it("keeps Book Edit as the contextual parent for related Group and Shelf links", () => {
    const editTrail = bookEditBreadcrumbTrail(bookDetailBreadcrumbFallback("Storm Front"), book.id, "Storm Front");
    expect(bookEditRelatedBreadcrumbTrail(
      editTrail,
      `/library/books/${book.id}/edit?tab=group-shelves`,
      { label: "Group Shelf", icon: "shelf" },
    ).slice(-2)).toEqual([
      { label: "Edit", to: `/library/books/${book.id}/edit?tab=group-shelves` },
      { label: "Group Shelf", icon: "shelf" },
    ]);
  });

  it("extends Book context through Shelf previews and Group links", () => {
    const detailTrail = bookDetailBreadcrumbFallback("Storm Front");
    expect(bookShelfPreviewBreadcrumbTrail(
      detailTrail, book.id, "Storm Front", "shelf/id", "Favorites", "Preview Book",
    ).slice(-3)).toEqual([
      { label: "Storm Front", to: `/library/books/${book.id}`, icon: "book" },
      { label: "Favorites", to: "/shelves/shelf%2Fid", icon: "shelf" },
      { label: "Preview Book", icon: "book" },
    ]);
    expect(bookGroupBreadcrumbTrail(detailTrail, book.id, "Storm Front", "Common Room", true).slice(-3)).toEqual([
      { label: "Storm Front", to: `/library/books/${book.id}`, icon: "book" },
      { label: "Groups", to: `/library/books/${book.id}?tab=groups`, icon: "group" },
      { label: "Common Room", icon: "public-group" },
    ]);
    expect(bookGroupPreviewBreadcrumbTrail(
      detailTrail, book.id, "Storm Front", "group-id", "Common Room", "Preview Book", true,
    ).slice(-4)).toEqual([
      { label: "Storm Front", to: `/library/books/${book.id}`, icon: "book" },
      { label: "Groups", to: `/library/books/${book.id}?tab=groups`, icon: "group" },
      { label: "Common Room", to: "/groups/group-id", icon: "public-group" },
      { label: "Preview Book", icon: "book" },
    ]);
  });

  it("falls back safely when incoming breadcrumb state is invalid or stale", () => {
    const fallback = bookDetailBreadcrumbFallback("Battle Ground");
    expect(resolveBreadcrumbTrail({ breadcrumbTrail: [{ label: "Unsafe", to: "https://example.test" }] }, fallback)).toEqual(fallback);
    expect(resolveBreadcrumbTrail({ breadcrumbContextId: "previous-runtime", breadcrumbTrail: [{ label: "Old" }] }, fallback)).toEqual(fallback);
  });
});
