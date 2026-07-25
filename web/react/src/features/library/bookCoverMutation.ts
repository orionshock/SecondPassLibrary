import type { BookDetail } from "@second-pass/spl-api";

export function bookDetailWithUpdatedCover(current: BookDetail, updated: BookDetail): BookDetail {
  return { ...current, coverUrl: updated.coverUrl };
}

export function confirmBookCoverClear(confirm: (message: string) => boolean = window.confirm): boolean {
  return confirm("Clear this Book cover?");
}
