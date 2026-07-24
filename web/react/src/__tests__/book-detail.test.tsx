import type { ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ApiError, type BookDetail } from "@second-pass/spl-api";
import { resolveBreadcrumbTrail } from "../app/navigation/breadcrumbs";
import { loadBookDetail } from "../features/library/BookDetailOrchestrator";
import {
  bookBrowseDetailBreadcrumbs,
  bookDetailBreadcrumbFallback,
  bookIdentifierLabel,
  bookSeriesDisplay,
  formatBookFileSize,
  formatBookPublishedDate,
} from "../features/library/bookDetailPresentation";
import { BookDetailHeroPageRegion } from "../features/library/regions/BookDetailHeroPageRegion";
import { BookDetailMetadataPageRegion } from "../features/library/regions/BookDetailMetadataPageRegion";
import { BookDetailStatePageRegion } from "../features/library/regions/BookDetailStatePageRegion";

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

  it("renders the read-only identity, escaped description, Catalog Tags, links, and one download action", () => {
    const markup = render(<BookDetailHeroPageRegion book={book} />);
    for (const text of ["Battle Ground", "A Novel of the Dresden Files", "Jim Butcher", "Dresden Files #18.00", "Penguin", "eng", "2020-07-14", "Fantasy"]) expect(markup).toContain(text);
    expect(markup).toContain("&lt;p&gt;hello&lt;/p&gt;");
    expect(markup).not.toContain("<p>hello</p>");
    expect(markup).toContain('href="/library?view=authors&amp;author=22222222-2222-4222-8222-222222222222"');
    expect(markup).toContain('href="/library?view=series&amp;series=33333333-3333-4333-8333-333333333333"');
    expect(markup).toContain('href="/download/book.epub"');
    expect(markup.match(/Download EPUB/g)).toHaveLength(1);
    expect(markup).toContain("No cover available for Battle Ground");
    for (const forbidden of ["DO-NOT-RENDER", "Edit", "Delete", "Read", "Open", "Change Cover"]) expect(markup).not.toContain(forbidden);
  });

  it("renders mapped metadata and read-only groups only in advanced mode", () => {
    const simple = render(<BookDetailMetadataPageRegion book={book} advancedGroupsEnabled={false} />);
    expect(simple).toContain("EPUB");
    expect(simple).toContain("1.5 KB");
    expect(simple).toContain("ISBN-13");
    expect(simple).toContain("9781234567890");
    expect(simple).not.toContain("Visible Groups");
    expect(simple).not.toContain("DO-NOT-RENDER");

    const advanced = render(<BookDetailMetadataPageRegion book={book} advancedGroupsEnabled />);
    expect(advanced).toContain("Visible Groups");
    expect(advanced).toContain("Common Room (Public)");
    expect(advanced).toContain("Everyone reads here");
    expect(advanced).not.toContain("Remove");
  });

  it("treats a null file projection as an EPUB repair state and omits download", () => {
    const repairBook = { ...book, file: null };
    const hero = render(<BookDetailHeroPageRegion book={repairBook} />);
    const metadata = render(<BookDetailMetadataPageRegion book={repairBook} advancedGroupsEnabled={false} />);
    expect(metadata).toContain("This book’s EPUB file is unavailable.");
    expect(metadata).not.toContain("No file");
    expect(hero).not.toContain("Download EPUB");
    expect(render(<BookDetailHeroPageRegion book={{ ...book, file: { ...book.file!, downloadUrl: "" } }} />)).not.toContain("Download EPUB");
  });

  it("omits blank optional metadata rather than leaving empty panels and rows", () => {
    const sparse = { ...book, subtitle: "", authors: [], series: null, publisher: "", language: "", publishedYear: null, description: "", identifiers: [], catalogTags: [] };
    const hero = render(<BookDetailHeroPageRegion book={sparse} />);
    const metadata = render(<BookDetailMetadataPageRegion book={sparse} advancedGroupsEnabled={false} />);
    expect(hero).not.toContain("Publisher:");
    expect(hero).not.toContain('aria-label="Catalog Tags"');
    expect(metadata).not.toContain("<h2>Metadata</h2>");
    expect(metadata).not.toContain("Identifiers");
    expect(metadata).toContain("EPUB File");
  });
});

describe("Book Detail orchestration and navigation", () => {
  it("loads a direct Book id exactly once through the supplied SDK boundary", async () => {
    const request = vi.fn(async () => book);
    await expect(loadBookDetail(book.id, request)).resolves.toBe(book);
    expect(request).toHaveBeenCalledOnce();
    expect(request).toHaveBeenCalledWith(book.id);
  });

  it("renders loading, bounded not-found, and retryable error states", () => {
    expect(render(<BookDetailStatePageRegion state="loading" />)).toContain("Loading book");
    expect(render(<BookDetailStatePageRegion state="not-found" />)).toContain("Book not found or unavailable.");
    const retry = vi.fn();
    const errorMarkup = render(<BookDetailStatePageRegion state="error" error={new Error("Temporarily unavailable")} onRetry={retry} />);
    expect(errorMarkup).toContain("Temporarily unavailable");
    expect(errorMarkup).toContain("Retry");
    const region = BookDetailStatePageRegion({ state: "error", error: new Error("Broken"), onRetry: retry }) as ReactElement<{ children: ReactElement[] }>;
    const retryButton = region.props.children[1] as ReactElement<{ onClick: () => void }>;
    retryButton.props.onClick();
    expect(retry).toHaveBeenCalledOnce();
  });

  it("preserves SDK 404 identity for the Orchestrator to collapse into unavailable", async () => {
    const error = new ApiError("Not found", 404);
    await expect(loadBookDetail(book.id, async () => { throw error; })).rejects.toBe(error);
  });

  it("builds direct, Books, selected Author, and selected Series breadcrumb trails", () => {
    expect(bookDetailBreadcrumbFallback("Battle Ground").map(({ label }) => label)).toEqual(["Library", "Books", "Battle Ground"]);
    expect(bookBrowseDetailBreadcrumbs({ title: "Battle Ground", libraryPath: "/library?q=battle" })).toEqual([
      { label: "Library", to: "/library" },
      { label: "Books", to: "/library?q=battle" },
      { label: "Battle Ground" },
    ]);
    expect(bookBrowseDetailBreadcrumbs({ title: "Battle Ground", libraryPath: "/library?view=authors&author=id", contextLabel: "Jim Butcher", parentLibraryPath: "/library?view=authors" }).map(({ label }) => label)).toEqual(["Library", "Jim Butcher", "Battle Ground"]);
    expect(bookBrowseDetailBreadcrumbs({ title: "Battle Ground", libraryPath: "/library?view=series&series=id", contextLabel: "Dresden Files", parentLibraryPath: "/library?view=series" }).map(({ label }) => label)).toEqual(["Library", "Dresden Files", "Battle Ground"]);
  });

  it("falls back safely when incoming breadcrumb state is invalid or stale", () => {
    const fallback = bookDetailBreadcrumbFallback("Battle Ground");
    expect(resolveBreadcrumbTrail({ breadcrumbTrail: [{ label: "Unsafe", to: "https://example.test" }] }, fallback)).toEqual(fallback);
    expect(resolveBreadcrumbTrail({ breadcrumbContextId: "previous-runtime", breadcrumbTrail: [{ label: "Old" }] }, fallback)).toEqual(fallback);
  });
});
