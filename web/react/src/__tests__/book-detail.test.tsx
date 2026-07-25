import type { ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { BookDetail } from "@second-pass/spl-api";
import { breadcrumbLinkState, resolveBreadcrumbTrail } from "../app/navigation/breadcrumbs";
import {
  bookBrowseDetailBreadcrumbs,
  bookDetailBreadcrumbFallback,
  bookEditBreadcrumbTrail,
  bookIdentifierLabel,
  bookSeriesDisplay,
  formatBookFileSize,
  formatBookPublishedDate,
} from "../features/library/bookDetailPresentation";
import { BookDetailHeroPageRegion } from "../features/library/regions/BookDetailHeroPageRegion";
import { BookDetailSectionsPageRegion } from "../features/library/regions/BookDetailSectionsPageRegion";

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
  groups: [{ id: "group", name: "Common Room", description: "Everyone reads here", isPublicGroup: true }],
};

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
    const metadata = render(<BookDetailSectionsPageRegion book={book} advancedGroupsEnabled={false} initialSection="metadata" />);
    expect(metadata).toContain("DO-NOT-RENDER");
    expect(metadata).toContain("9781234567890");
  });

  it("uses the server-provided advanced-groups mode to gate visible groups", () => {
    const simple = render(<BookDetailSectionsPageRegion book={book} advancedGroupsEnabled={false} initialSection="groups" />);
    const advanced = render(<BookDetailSectionsPageRegion book={book} advancedGroupsEnabled initialSection="groups" />);
    expect(simple).not.toContain("Common Room");
    expect(advanced).toContain("Common Room");
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
});

describe("Book Detail navigation", () => {
  it("builds direct, Books, selected Author, and selected Series breadcrumb trails", () => {
    expect(bookDetailBreadcrumbFallback("Battle Ground").map(({ label }) => label)).toEqual(["Library", "Books", "Battle Ground"]);
    expect(bookBrowseDetailBreadcrumbs({ title: "Battle Ground", libraryPath: "/library?q=battle" })).toEqual([
      { label: "Library", to: "/library", resetTrail: true },
      { label: "Books", to: "/library?q=battle", resetTrail: true },
      { label: "Battle Ground" },
    ]);
    expect(bookBrowseDetailBreadcrumbs({ title: "Battle Ground", libraryPath: "/library?view=authors&author=id", contextLabel: "Jim Butcher", parentLibraryPath: "/library?view=authors" }).map(({ label }) => label)).toEqual(["Library", "Jim Butcher", "Battle Ground"]);
    expect(bookBrowseDetailBreadcrumbs({ title: "Battle Ground", libraryPath: "/library?view=series&series=id", contextLabel: "Dresden Files", parentLibraryPath: "/library?view=series" }).map(({ label }) => label)).toEqual(["Library", "Dresden Files", "Battle Ground"]);
    expect(bookEditBreadcrumbTrail(bookDetailBreadcrumbFallback("Old title"), book.id, "New title")).toEqual([
      { label: "Library", to: "/library", resetTrail: true }, { label: "Books", to: "/library", resetTrail: true },
      { label: "New title", to: `/library/books/${book.id}` }, { label: "Edit" },
    ]);
  });

  it("preserves selected browse context when following the Book ancestor from Edit", () => {
    const editTrail = bookEditBreadcrumbTrail(
      bookBrowseDetailBreadcrumbs({
        title: "Storm Front",
        libraryPath: "/library?view=series&series=series-id",
        contextLabel: "Dresden Files",
        parentLibraryPath: "/library?view=series",
      }),
      book.id,
      "Storm Front",
    );
    expect(resolveBreadcrumbTrail(breadcrumbLinkState(editTrail, editTrail.length - 2), [])).toEqual([
      { label: "Library", to: "/library?view=series" },
      { label: "Dresden Files", to: "/library?view=series&series=series-id" },
      { label: "Storm Front", to: `/library/books/${book.id}` },
    ]);
  });

  it("falls back safely when incoming breadcrumb state is invalid or stale", () => {
    const fallback = bookDetailBreadcrumbFallback("Battle Ground");
    expect(resolveBreadcrumbTrail({ breadcrumbTrail: [{ label: "Unsafe", to: "https://example.test" }] }, fallback)).toEqual(fallback);
    expect(resolveBreadcrumbTrail({ breadcrumbContextId: "previous-runtime", breadcrumbTrail: [{ label: "Old" }] }, fallback)).toEqual(fallback);
  });
});
