import { describe, expect, it } from "vitest";

import type { BookDetail } from "@second-pass/spl-api";
import { LocalValidationError } from "../shared/feedback/mutationState";
import { bookEditDraftFromBook, bookEditDraftsEqual, bookEditInputFromDraft, validateBookEditDraft } from "../features/library/bookEditDraft";

const book: BookDetail = {
  id: "book", title: "Book", sortTitle: "Book, The", subtitle: "Sub", description: "Text",
  authors: [{ id: "a1", name: "Author One" }, { id: "a2", name: "Author Two" }],
  series: { id: "s1", name: "Series", sortName: "Series", seriesIndex: "2.0" },
  publisher: "Press", language: "eng", publishedYear: 2025, publishedMonth: 2, publishedDay: 28,
  publishedDatePrecision: "day", coverUrl: null, catalogTags: [{ id: "t1", name: "Fantasy", slug: "fantasy" }],
  identifiers: [], file: null, groups: [],
};

describe("Book Edit draft contract", () => {
  it("initializes ordered relationship and date state and builds the explicit replacement payload", () => {
    const draft = bookEditDraftFromBook(book);
    expect(draft).toMatchObject({ authorIds: ["a1", "a2"], seriesId: "s1", seriesIndex: "2.0", publishedYear: "2025", publishedMonth: "2", publishedDay: "28", catalogTagNames: ["Fantasy"] });
    expect(bookEditInputFromDraft(draft)).toEqual({
      title: "Book", sortTitle: "Book, The", subtitle: "Sub", description: "Text", publisher: "Press", language: "eng",
      publishedDatePrecision: "day", publishedYear: 2025, publishedMonth: 2, publishedDay: 28,
      authorIds: ["a1", "a2"], seriesId: "s1", seriesIndex: "2.0", catalogTagNames: ["Fantasy"],
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
    ];
    for (const draft of cases) expect(() => validateBookEditDraft(draft)).toThrow(LocalValidationError);
  });
});
