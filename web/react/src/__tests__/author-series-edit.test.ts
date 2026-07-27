import { describe, expect, it } from "vitest";

import type { LibraryAuthor, LibrarySeries } from "@second-pass/spl-api";
import {
  authorEditDraft,
  authorMutationInput,
  authorSeriesEditDraftsEqual,
  emptyAuthorSeriesEditDraft,
  seriesEditDraft,
  seriesMutationInput,
  validateAuthorSeriesEditDraft,
} from "../features/library/authorSeriesEditDraft";
import {
  libraryEntityBreadcrumbs,
  libraryEntityContextPath,
  libraryEntityEditPath,
  libraryEntityNavigationState,
  readLibraryEntityReturnTo,
} from "../features/library/authorSeriesLifecycle";
import { LocalValidationError } from "../shared/feedback/mutationState";

const author: LibraryAuthor = { id: "author", name: "Ada", sortName: "Author, Ada", biography: "Bio", bookCount: 2 };
const series: LibrarySeries = { id: "series", name: "Saga", sortName: "Saga", summary: "Summary", bookCount: 1 };

describe("Author and Series lifecycle draft contract", () => {
  it("initializes blank and existing drafts and maps the exact mutation domains", () => {
    expect(emptyAuthorSeriesEditDraft).toEqual({ name: "", sortName: "", prose: "" });
    expect(authorEditDraft(author)).toEqual({ name: "Ada", sortName: "Author, Ada", prose: "Bio" });
    expect(seriesEditDraft(series)).toEqual({ name: "Saga", sortName: "Saga", prose: "Summary" });
    expect(authorMutationInput({ name: " Ada ", sortName: " Author, Ada ", prose: " Bio " })).toEqual({ name: "Ada", sortName: "Author, Ada", biography: " Bio " });
    expect(seriesMutationInput({ name: " Saga ", sortName: " ", prose: "Summary" })).toEqual({ name: "Saga", sortName: "", summary: "Summary" });
  });

  it("rejects only meaningful local field invariants and normalizes dirty comparison", () => {
    for (const draft of [
      { name: " ", sortName: "", prose: "" },
      { name: "x".repeat(256), sortName: "", prose: "" },
      { name: "Valid", sortName: "x".repeat(256), prose: "" },
    ]) expect(() => validateAuthorSeriesEditDraft(draft)).toThrow(LocalValidationError);
    expect(() => validateAuthorSeriesEditDraft({ name: "Duplicate Allowed", sortName: "", prose: "" })).not.toThrow();
    expect(authorSeriesEditDraftsEqual(
      { name: "Ada", sortName: "Author, Ada", prose: "Bio" },
      { name: " Ada ", sortName: " Author, Ada ", prose: "Bio" },
    )).toBe(true);
  });

  it("encodes lifecycle paths and accepts only safe internal return destinations", () => {
    expect(libraryEntityEditPath("author", "author/id")).toBe("/library/authors/author%2Fid/edit");
    expect(libraryEntityContextPath("author", "author/id")).toBe("/library?view=authors&author=author%2Fid");
    expect(libraryEntityBreadcrumbs("author", "edit", "Ada", "author/id")[2]).toEqual({
      label: "Ada",
      to: "/library?view=authors&author=author%2Fid",
      icon: "author",
    });
    const safe = libraryEntityNavigationState({ breadcrumbs: [{ label: "Author" }], returnTo: "/library?view=authors" });
    const unsafe = libraryEntityNavigationState({ breadcrumbs: [{ label: "Author" }], returnTo: "https://example.com" });
    expect(readLibraryEntityReturnTo(safe)).toBe("/library?view=authors");
    expect(readLibraryEntityReturnTo(unsafe)).toBeUndefined();
  });
});
