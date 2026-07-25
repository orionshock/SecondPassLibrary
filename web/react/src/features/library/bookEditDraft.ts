import {
  bookIdentifierSchemes,
  type BookDetail,
  type BookIdentifierScheme,
  type UpdateBookInput,
} from "@second-pass/spl-api";

import { LocalValidationError } from "../../shared/feedback/mutationState";

export type PublicationPrecision = "" | "year" | "month" | "day";

export interface BookIdentifierDraft {
  key: string;
  scheme: BookIdentifierScheme;
  value: string;
}

export const bookIdentifierSchemeOptions: readonly BookIdentifierScheme[] = bookIdentifierSchemes;

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
  identifiers: BookIdentifierDraft[];
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
    identifiers: book.identifiers.map(({ id, scheme, value }) => ({
      key: id,
      scheme: isBookIdentifierScheme(scheme) ? scheme : "other",
      value,
    })),
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
    identifiers: draft.identifiers.map((identifier) => ({
      ...identifier,
      value: identifier.value.trim(),
    })),
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
    identifiers: draft.identifiers.map(({ scheme, value }) => ({ scheme, value })),
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
  const identifierKeys = new Set<string>();
  draft.identifiers.forEach((identifier, index) => {
    if (!isBookIdentifierScheme(identifier.scheme)) {
      errors[`identifiers.${index}.scheme`] = ["Choose a valid identifier scheme."];
    }
    if (!identifier.value) {
      errors[`identifiers.${index}.value`] = ["Enter an identifier value."];
    } else if (identifier.value.length > 512) {
      errors[`identifiers.${index}.value`] = ["Use 512 characters or fewer."];
    }
    const duplicateKey = `${identifier.scheme}\u0000${collapseIdentifierValue(identifier.value).toLowerCase()}`;
    if (identifier.value && identifierKeys.has(duplicateKey)) {
      errors[`identifiers.${index}.value`] = ["This identifier is already in the draft."];
    }
    identifierKeys.add(duplicateKey);
  });
  if (Object.keys(errors).length) throw new LocalValidationError("Check the highlighted fields.", errors);
}

export function bookEditDraftsEqual(left: BookEditDraft, right: BookEditDraft): boolean {
  return JSON.stringify(comparableBookEditDraft(left)) === JSON.stringify(comparableBookEditDraft(right));
}

function comparableBookEditDraft(value: BookEditDraft) {
  const draft = normalizeBookEditDraft(value);
  return {
    ...draft,
    identifiers: draft.identifiers.map(({ scheme, value }) => ({ scheme, value })),
  };
}

function isPublicationPrecision(value: string): value is PublicationPrecision {
  return value === "" || value === "year" || value === "month" || value === "day";
}

function isBookIdentifierScheme(value: string): value is BookIdentifierScheme {
  return (bookIdentifierSchemes as readonly string[]).includes(value);
}

function collapseIdentifierValue(value: string): string {
  return value.trim().replace(/\s+/g, " ");
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
