import type { BookSeriesSummary } from "@second-pass/spl-api";

import type { BreadcrumbItem } from "../../app/navigation/breadcrumbs";

const identifierLabels: Record<string, string> = {
  asin: "ASIN",
  calibre: "Calibre",
  doi: "DOI",
  epub_uid: "EPUB UID",
  isbn_10: "ISBN-10",
  isbn_13: "ISBN-13",
  lccn: "LCCN",
  oclc: "OCLC",
  openlibrary: "Open Library",
  other: "Other",
  publisher: "Publisher",
  uri: "URI/URN",
  uuid: "UUID",
};

export function formatBookPublishedDate(book: {
  publishedYear: number | null;
  publishedMonth: number | null;
  publishedDay: number | null;
  publishedDatePrecision: string;
}): string | undefined {
  if (book.publishedYear === null) return undefined;
  const year = String(book.publishedYear).padStart(4, "0");
  const month = book.publishedMonth === null ? undefined : String(book.publishedMonth).padStart(2, "0");
  const day = book.publishedDay === null ? undefined : String(book.publishedDay).padStart(2, "0");
  if (book.publishedDatePrecision === "day" && month && day) return `${year}-${month}-${day}`;
  if (book.publishedDatePrecision === "month" && month) return `${year}-${month}`;
  return year;
}

export function formatBookFileSize(bytes: number | null): string | undefined {
  if (bytes === null || !Number.isFinite(bytes) || bytes < 0) return undefined;
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  const rounded = value >= 10 ? Math.round(value) : Math.round(value * 10) / 10;
  return `${rounded} ${units[unitIndex]}`;
}

export function bookSeriesDisplay(series: BookSeriesSummary): string {
  return series.seriesIndex ? `${series.name} #${series.seriesIndex}` : series.name;
}

export function bookIdentifierLabel(scheme: string): string {
  return identifierLabels[scheme] ?? scheme.replaceAll("_", " ");
}

export function bookDetailBreadcrumbFallback(title = "Book"): BreadcrumbItem[] {
  return [
    { label: "Library", to: "/library", resetTrail: true },
    { label: "Books", to: "/library", resetTrail: true },
    { label: title },
  ];
}

export function bookEditBreadcrumbTrail(detailTrail: readonly BreadcrumbItem[], bookId: string, title: string): BreadcrumbItem[] {
  const withoutEdit = detailTrail.at(-1)?.label === "Edit" ? detailTrail.slice(0, -1) : [...detailTrail];
  const parent = withoutEdit.length > 0 ? withoutEdit.slice(0, -1) : bookDetailBreadcrumbFallback(title).slice(0, -1);
  return [...parent, { label: title, to: `/library/books/${encodeURIComponent(bookId)}` }, { label: "Edit" }];
}

export function bookShelfBreadcrumbTrail(
  detailTrail: readonly BreadcrumbItem[],
  bookId: string,
  bookTitle: string,
  shelfName: string,
): BreadcrumbItem[] {
  const resolvedDetailTrail = detailTrail.length > 0 ? detailTrail : bookDetailBreadcrumbFallback(bookTitle);
  return [
    ...resolvedDetailTrail.slice(0, -1),
    { label: bookTitle, to: `/library/books/${encodeURIComponent(bookId)}` },
    { label: shelfName },
  ];
}

export function bookBrowseDetailBreadcrumbs({
  title,
  libraryPath,
  contextLabel,
  parentLibraryPath = libraryPath,
}: {
  title: string;
  libraryPath: string;
  contextLabel?: string;
  parentLibraryPath?: string;
}): BreadcrumbItem[] {
  if (contextLabel) {
    return [
      { label: "Library", to: parentLibraryPath, resetTrail: true },
      { label: contextLabel, to: libraryPath },
      { label: title },
    ];
  }
  return [
    { label: "Library", to: "/library", resetTrail: true },
    { label: "Books", to: libraryPath, resetTrail: true },
    { label: title },
  ];
}
