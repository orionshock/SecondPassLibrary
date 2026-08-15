import { describe, expect, it } from "vitest";

import type { LibraryAuthor, LibrarySeries } from "@second-pass/spl-api";
import { breadcrumbNavigationState, resolveBreadcrumbTrail } from "../../../../src/app/navigation/breadcrumbs";
import {
  authorEditDraft,
  authorMutationInput,
  authorSeriesEditDraftsEqual,
  emptyAuthorSeriesEditDraft,
  seriesEditDraft,
  seriesMutationInput,
  validateAuthorSeriesEditDraft,
} from "../../../../src/features/library/authorSeriesEdit/authorSeriesEditDraft";
import {
  libraryEntityBreadcrumbs,
  libraryEntityAxisPath,
  libraryEntityAttachedBookBreadcrumbs,
  libraryEntityContextBreadcrumbs,
  libraryEntityContextPath,
  libraryEntityEditPath,
  libraryEntityNavigationState,
  libraryEntityParentBreadcrumbs,
  libraryEntitySavedBreadcrumbs,
  readLibraryEntityReturnTo,
} from "../../../../src/features/library/authorSeriesLifecycle";
import { LocalValidationError } from "../../../../src/shared/feedback/mutationState";

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
    expect(libraryEntityAxisPath("author")).toBe("/library?view=authors");
    expect(libraryEntityAxisPath("series")).toBe("/library?view=series");
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

  it("preserves a Book Edit breadcrumb context through lifecycle navigation", () => {
    const parent = [
      { label: "Library", to: "/library", icon: "library" as const },
      { label: "Books", to: "/library", icon: "book" as const },
      { label: "Battle Ground", to: "/library/books/book", icon: "book" as const },
      { label: "Edit" },
    ];
    const returnTo = "/library/books/book/edit?tab=authors-series";
    const createTrail = libraryEntityContextBreadcrumbs(parent, "author", "new", returnTo);
    expect(createTrail.at(-2)).toEqual({ label: "Edit", to: returnTo });
    expect(createTrail.at(-1)).toEqual({ label: "New Author", icon: "author" });

    const savedTrail = libraryEntitySavedBreadcrumbs(createTrail, "author", "Ada", "author/id");
    expect(savedTrail.slice(-3)).toEqual([
      { label: "Edit", to: returnTo },
      { label: "Ada", to: "/library?view=authors&author=author%2Fid", icon: "author" },
      { label: "Edit" },
    ]);
    expect(libraryEntityParentBreadcrumbs(savedTrail, "author", "edit")).toEqual(parent.map((item, index) => (
      index === parent.length - 1 ? { ...item, to: returnTo } : item
    )));
  });

  it("extends the resolved edit trail when an attached Book is selected", () => {
    const editTrail = [
      { label: "Library", to: "/library", icon: "library" as const },
      { label: "Authors", to: "/library?view=authors", icon: "author" as const },
      { label: "Ada", to: "/library?view=authors&author=author", icon: "author" as const },
      { label: "Edit" },
    ];

    const attachedBookTrail = libraryEntityAttachedBookBreadcrumbs(
      editTrail,
      "/library/authors/author/edit",
      "Selected Book",
    );
    expect(attachedBookTrail).toEqual([
      ...editTrail.slice(0, -1),
      { label: "Edit", to: "/library/authors/author/edit" },
      { label: "Selected Book", icon: "book" },
    ]);
    expect(resolveBreadcrumbTrail(
      breadcrumbNavigationState(attachedBookTrail),
      [{ label: "Reset fallback" }],
    )).toEqual(attachedBookTrail);
  });
});

