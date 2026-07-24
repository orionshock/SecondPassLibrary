import type { BookDetail, UpdateBookInput } from "@second-pass/spl-api";

import { LocalValidationError } from "../../shared/feedback/mutationState";

export type PublicationPrecision = "" | "year" | "month" | "day";

export interface BookEditDraft {
  title: string;
  sortTitle: string;
  subtitle: string;
  description: string;
  publisher: string;
  language: string;
  publishedYear: string;
  publishedMonth: string;
  publishedDay: string;
  publishedDatePrecision: PublicationPrecision;
  authorIds: string[];
  seriesId: string | null;
  seriesIndex: string;
  catalogTagNames: string[];
}

export function bookEditDraftFromBook(book: BookDetail): BookEditDraft {
  return {
    title: book.title,
    sortTitle: book.sortTitle,
    subtitle: book.subtitle,
    description: book.description,
    publisher: book.publisher,
    language: book.language,
    publishedYear: book.publishedYear?.toString() ?? "",
    publishedMonth: book.publishedMonth?.toString() ?? "",
    publishedDay: book.publishedDay?.toString() ?? "",
    publishedDatePrecision: isPublicationPrecision(book.publishedDatePrecision) ? book.publishedDatePrecision : "",
    authorIds: book.authors.map(({ id }) => id),
    seriesId: book.series?.id ?? null,
    seriesIndex: book.series?.seriesIndex ?? "",
    catalogTagNames: book.catalogTags.map(({ name }) => name),
  };
}

export function normalizeBookEditDraft(draft: BookEditDraft): BookEditDraft {
  const precision = draft.publishedDatePrecision;
  return {
    ...draft,
    title: draft.title.trim(),
    authorIds: unique(draft.authorIds),
    seriesIndex: draft.seriesId ? draft.seriesIndex.trim() : "",
    catalogTagNames: uniqueNames(draft.catalogTagNames),
    publishedYear: precision ? draft.publishedYear.trim() : "",
    publishedMonth: precision === "month" || precision === "day" ? draft.publishedMonth.trim() : "",
    publishedDay: precision === "day" ? draft.publishedDay.trim() : "",
  };
}

export function bookEditInputFromDraft(value: BookEditDraft): UpdateBookInput {
  const draft = normalizeBookEditDraft(value);
  return {
    title: draft.title,
    sortTitle: draft.sortTitle,
    subtitle: draft.subtitle,
    description: draft.description,
    publisher: draft.publisher,
    language: draft.language,
    publishedDatePrecision: draft.publishedDatePrecision,
    publishedYear: toNumberOrNull(draft.publishedYear),
    publishedMonth: draft.publishedDatePrecision === "month" || draft.publishedDatePrecision === "day" ? toNumberOrNull(draft.publishedMonth) : null,
    publishedDay: draft.publishedDatePrecision === "day" ? toNumberOrNull(draft.publishedDay) : null,
    authorIds: draft.authorIds,
    seriesId: draft.seriesId,
    seriesIndex: draft.seriesId && draft.seriesIndex ? draft.seriesIndex : null,
    catalogTagNames: draft.catalogTagNames,
  };
}

export function validateBookEditDraft(value: BookEditDraft): void {
  const draft = normalizeBookEditDraft(value);
  const errors: Record<string, string[]> = {};
  requiredMax(errors, "title", draft.title, 512, "Enter a title.");
  max(errors, "sortTitle", draft.sortTitle, 512);
  max(errors, "subtitle", draft.subtitle, 512);
  max(errors, "publisher", draft.publisher, 255);
  max(errors, "language", draft.language, 64);

  const year = integer(draft.publishedYear);
  const month = integer(draft.publishedMonth);
  const day = integer(draft.publishedDay);
  if (draft.publishedDatePrecision && year === undefined) errors.publishedYear = ["Enter a valid year."];
  if ((draft.publishedDatePrecision === "month" || draft.publishedDatePrecision === "day") && (month === undefined || month < 1 || month > 12)) {
    errors.publishedMonth = ["Enter a month from 1 to 12."];
  }
  if (draft.publishedDatePrecision === "day") {
    if (day === undefined || year === undefined || month === undefined || day < 1 || day > daysInMonth(year, month)) {
      errors.publishedDay = ["Enter a valid calendar day."];
    }
  }

  if (new Set(value.authorIds).size !== value.authorIds.length) errors.authorIds = ["Each author may be assigned once."];
  if (!value.seriesId && value.seriesIndex.trim()) errors.seriesIndex = ["Choose a Series before entering an index."];
  if (draft.seriesIndex && (!/^\d+(?:\.\d)?$/.test(draft.seriesIndex) || Number(draft.seriesIndex) <= 0)) {
    errors.seriesIndex = ["Enter a positive value with at most one decimal place."];
  }
  if (Object.keys(errors).length) throw new LocalValidationError("Check the highlighted fields.", errors);
}

export function bookEditDraftsEqual(left: BookEditDraft, right: BookEditDraft): boolean {
  return JSON.stringify(normalizeBookEditDraft(left)) === JSON.stringify(normalizeBookEditDraft(right));
}

function isPublicationPrecision(value: string): value is PublicationPrecision {
  return value === "" || value === "year" || value === "month" || value === "day";
}

function unique(values: string[]): string[] {
  return [...new Set(values)];
}

function uniqueNames(values: string[]): string[] {
  const seen = new Set<string>();
  return values.map((name) => name.trim()).filter((name) => {
    const key = name.toLocaleLowerCase();
    if (!name || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function toNumberOrNull(value: string): number | null {
  return value === "" ? null : Number(value);
}

function integer(value: string): number | undefined {
  if (!/^\d+$/.test(value)) return undefined;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : undefined;
}

function daysInMonth(year: number, month: number): number {
  if (month === 2) return year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0) ? 29 : 28;
  return [4, 6, 9, 11].includes(month) ? 30 : 31;
}

function max(errors: Record<string, string[]>, field: string, value: string, limit: number): void {
  if (value.length > limit) errors[field] = [`Use ${limit} characters or fewer.`];
}

function requiredMax(errors: Record<string, string[]>, field: string, value: string, limit: number, required: string): void {
  if (!value) errors[field] = [required];
  else max(errors, field, value, limit);
}
