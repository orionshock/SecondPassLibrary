import { describe, expect, it } from "vitest";

import type { BookDetail, BookIdentifierScheme, CurrentUser } from "@second-pass/spl-api";
import { LocalValidationError } from "../shared/feedback/mutationState";
import { bookDetailWithUpdatedCover } from "../features/library/bookCoverMutation";
import { bookDetailWithUpdatedGroups, canEditBookGroups } from "../features/library/bookGroupMutation";
import { bookEditDraftFromBook, bookEditDraftsEqual, bookEditInputFromDraft, validateBookEditDraft } from "../features/library/bookEditDraft";

const book: BookDetail = {
  id: "book", title: "Book", sortTitle: "Book, The", subtitle: "Sub", description: "Text",
  authors: [{ id: "a1", name: "Author One" }, { id: "a2", name: "Author Two" }],
  series: { id: "s1", name: "Series", sortName: "Series", seriesIndex: "2.0" },
  publisher: "Press", language: "eng", publishedYear: 2025, publishedMonth: 2, publishedDay: 28,
  publishedDatePrecision: "day", coverUrl: null, catalogTags: [{ id: "t1", name: "Fantasy", slug: "fantasy" }],
  identifiers: [{ id: "identifier-1", scheme: "isbn_13", value: "978123" }], file: null, groups: [],
};

describe("Book Edit draft contract", () => {
  it("initializes ordered relationship and date state and builds the explicit replacement payload", () => {
    const draft = bookEditDraftFromBook(book);
    expect(draft).toMatchObject({
      authorIds: ["a1", "a2"], seriesId: "s1", seriesIndex: "2.0",
      publishedYear: "2025", publishedMonth: "2", publishedDay: "28",
      identifiers: [{ key: "identifier-1", scheme: "isbn_13", value: "978123" }],
      catalogTagNames: ["Fantasy"],
    });
    expect(bookEditInputFromDraft(draft)).toEqual({
      title: "Book", sortTitle: "Book, The", subtitle: "Sub", description: "Text", publisher: "Press", language: "eng",
      publishedDatePrecision: "day", publishedYear: 2025, publishedMonth: 2, publishedDay: 28,
      authorIds: ["a1", "a2"], seriesId: "s1", seriesIndex: "2.0",
      identifiers: [{ scheme: "isbn_13", value: "978123" }], catalogTagNames: ["Fantasy"],
    });
    expect(bookEditDraftsEqual(draft, { ...draft, title: " Book ", catalogTagNames: ["Fantasy", "fantasy"] })).toBe(true);
  });

  it("normalizes explicit date and Series clears for the backend contract", () => {
    const draft = { ...bookEditDraftFromBook(book), publishedDatePrecision: "" as const, seriesId: null, seriesIndex: "2.0" };
    expect(bookEditInputFromDraft(draft)).toMatchObject({ publishedDatePrecision: "", publishedYear: null, publishedMonth: null, publishedDay: null, seriesId: null, seriesIndex: null });
  });

  it("rejects the local invariants that would make a save invalid", () => {
    const cases = [
      { ...bookEditDraftFromBook(book), title: " " },
      { ...bookEditDraftFromBook(book), publishedDay: "31" },
      { ...bookEditDraftFromBook(book), seriesIndex: "1.55" },
      { ...bookEditDraftFromBook(book), seriesId: null, seriesIndex: "1.0" },
      { ...bookEditDraftFromBook(book), authorIds: ["a1", "a1"] },
      { ...bookEditDraftFromBook(book), identifiers: [{ key: "blank", scheme: "doi" as const, value: " " }] },
      { ...bookEditDraftFromBook(book), identifiers: [{ key: "long", scheme: "doi" as const, value: "x".repeat(513) }] },
      { ...bookEditDraftFromBook(book), identifiers: [{ key: "bad", scheme: "not-a-scheme" as BookIdentifierScheme, value: "value" }] },
      { ...bookEditDraftFromBook(book), identifiers: [
        { key: "one", scheme: "doi" as const, value: "Example Value" },
        { key: "two", scheme: "doi" as const, value: " example   value " },
      ] },
    ];
    for (const draft of cases) expect(() => validateBookEditDraft(draft)).toThrow(LocalValidationError);
  });

  it("treats identifier add/remove and values as draft state, not server row identity", () => {
    const baseline = bookEditDraftFromBook(book);
    const added = {
      ...baseline,
      identifiers: [...baseline.identifiers, { key: "new-1", scheme: "doi" as const, value: "10.1000/example" }],
    };
    expect(bookEditDraftsEqual(baseline, added)).toBe(false);
    expect(bookEditDraftsEqual(baseline, { ...baseline, identifiers: [...baseline.identifiers] })).toBe(true);
    expect(bookEditDraftsEqual(
      baseline,
      { ...baseline, identifiers: baseline.identifiers.map((identifier) => ({ ...identifier, key: "replacement-key" })) },
    )).toBe(true);
    expect(bookEditInputFromDraft({ ...baseline, identifiers: [] }).identifiers).toEqual([]);
  });

  it("applies a cover mutation result without replacing metadata or its draft baseline", () => {
    const baseline = bookEditDraftFromBook(book);
    const dirtyDraft = { ...baseline, title: "Unsaved title" };
    const returned = {
      ...book,
      title: "Stale server title",
      authors: [],
      identifiers: [],
      coverUrl: "/media/new-cover.jpg",
    };

    expect(bookDetailWithUpdatedCover(book, returned)).toEqual({
      ...book,
      coverUrl: "/media/new-cover.jpg",
    });
    expect(dirtyDraft.title).toBe("Unsaved title");
    expect(baseline.title).toBe("Book");
  });

  it("limits group editing to advanced-mode catalog managers and merges only refreshed groups", () => {
    const librarian = {
      role: "librarian", isLibrarian: true, advancedLibraryGroupsEnabled: true,
    } as CurrentUser;
    expect(canEditBookGroups(librarian)).toBe(true);
    expect(canEditBookGroups({ ...librarian, advancedLibraryGroupsEnabled: false })).toBe(false);
    expect(canEditBookGroups({ ...librarian, role: "reader", isLibrarian: false, isReader: true })).toBe(false);

    const baseline = bookEditDraftFromBook(book);
    const dirtyDraft = { ...baseline, title: "Unsaved title" };
    const refreshed = { ...book, title: "Stale server title", groups: [{ id: "g1", name: "Readers", description: "", isPublicGroup: false }] };
    expect(bookDetailWithUpdatedGroups(book, refreshed)).toEqual({ ...book, groups: refreshed.groups });
    expect(dirtyDraft.title).toBe("Unsaved title");
    expect(baseline.title).toBe("Book");
  });
});
