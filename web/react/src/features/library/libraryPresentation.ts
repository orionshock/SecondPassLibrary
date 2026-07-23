import type { BookPreview, CompactBook } from "@second-pass/spl-api";

import { breadcrumbNavigationState } from "../../app/navigation/breadcrumbs";
import type { BookCoverPreviewItem } from "../../shared/books/BookCoverPreviewStripComponent";

export function bookAuthorNames(book: CompactBook): string[] {
  return book.authors.map(({ name }) => name);
}

export function bookSeriesLabel(book: CompactBook): string | undefined {
  if (!book.series) return undefined;
  return book.series.seriesIndex ? `${book.series.name} ${book.series.seriesIndex}` : book.series.name;
}

export function visibleCatalogTags(book: CompactBook, limit = 6) {
  return {
    tags: book.catalogTags.slice(0, limit),
    hiddenCount: Math.max(0, book.catalogTags.length - limit),
  };
}

export function previewBooksForLibrary(books: readonly BookPreview[] | undefined, libraryPath: string): BookCoverPreviewItem[] {
  return (books ?? []).slice(0, 6).map((book) => ({
    ...book,
    href: `/library/books/${encodeURIComponent(book.id)}`,
    navigationState: breadcrumbNavigationState([
      { label: "Library", to: libraryPath },
      { label: book.title },
    ]),
  }));
}
