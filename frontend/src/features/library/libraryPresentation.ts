import type { BookPreview, CompactBook } from "@second-pass/spl-api";

import { breadcrumbNavigationState } from "../../app/navigation/breadcrumbs";
import type { BookCoverPreviewItem } from "../../shared/books/BookCoverPreviewStrip";
import { COMPACT_BOOK_COVER_PREVIEW_SOURCE_LIMIT } from "../../shared/books/bookCoverPreview";
import type { LibrarySelectedContextKind, LibraryUrlState } from "./libraryQuery";

export interface SelectedLibraryContextDisplay {
  kind: LibrarySelectedContextKind;
  id: string;
  name: string;
  bookCount?: number;
}

export interface SelectedLibraryContextNavigationState {
  librarySelectedContext: SelectedLibraryContextDisplay;
}

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
  return (books ?? []).slice(0, COMPACT_BOOK_COVER_PREVIEW_SOURCE_LIMIT).map((book) => ({
    ...book,
    href: `/library/books/${encodeURIComponent(book.id)}`,
    navigationState: breadcrumbNavigationState([
      { label: "Library", to: libraryPath, icon: "library" },
      { label: book.title, icon: "book" },
    ]),
  }));
}

export function selectedLibraryContextNavigationState(context: SelectedLibraryContextDisplay): SelectedLibraryContextNavigationState {
  return { librarySelectedContext: context };
}

export function readSelectedLibraryContextDisplay(state: unknown, query: LibraryUrlState): SelectedLibraryContextDisplay | undefined {
  if (!isRecord(state) || !isRecord(state.librarySelectedContext)) return undefined;
  const context = state.librarySelectedContext;
  const kind = context.kind;
  const id = context.id;
  const name = typeof context.name === "string" ? context.name.trim() : "";
  if ((kind !== "author" && kind !== "series") || typeof id !== "string") return undefined;
  const matches = kind === "author" ? query.authorId === id : query.seriesId === id;
  if (!matches || !name) return undefined;
  return {
    kind,
    id,
    name,
    ...(typeof context.bookCount === "number" && context.bookCount >= 0 ? { bookCount: context.bookCount } : {}),
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
