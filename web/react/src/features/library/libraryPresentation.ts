import type { CompactBook } from "@second-pass/spl-api";

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
