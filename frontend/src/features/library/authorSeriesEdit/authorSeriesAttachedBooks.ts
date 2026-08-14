import type { BookPreview, CompactBook, LibraryBooksQuery } from "@second-pass/spl-api";

import type { LibraryEntityKind } from "../authorSeriesLifecycle";

export const ATTACHED_BOOK_PAGE_SIZE = 24;

export class AttachedBooksRequestGate {
  #key = "";
  #pending = false;

  reset(key: string): void {
    this.#key = key;
    this.#pending = false;
  }

  start(key: string): boolean {
    if (key !== this.#key || this.#pending) return false;
    this.#pending = true;
    return true;
  }

  isCurrent(key: string): boolean {
    return key === this.#key;
  }

  finish(key: string): void {
    if (key === this.#key) this.#pending = false;
  }
}

export function attachedBooksQuery(
  kind: LibraryEntityKind,
  entityId: string,
  page: number,
): LibraryBooksQuery {
  return {
    ...(kind === "author" ? { authorId: entityId } : { seriesId: entityId }),
    ordering: kind === "author" ? "title" : "series_index",
    page,
    pageSize: ATTACHED_BOOK_PAGE_SIZE,
  };
}

export function appendAttachedBooks(
  current: readonly BookPreview[],
  page: readonly CompactBook[],
): BookPreview[] {
  const byId = new Map(current.map((book) => [book.id, book]));
  for (const book of page) {
    if (!byId.has(book.id)) {
      byId.set(book.id, { id: book.id, title: book.title, coverUrl: book.coverUrl });
    }
  }
  return [...byId.values()];
}
