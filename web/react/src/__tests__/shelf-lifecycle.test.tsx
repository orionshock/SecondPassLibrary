import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { CurrentUser, LibraryGroup, ShelfSummary } from "@second-pass/spl-api";
import { ShelfRowComponent } from "../features/shelves/components/ShelfRowComponent";
import {
  createShelfInputFromDraft,
  emptyShelfDraft,
  shelfDraftFromSummary,
  shelfDraftsEqual,
  updateShelfInputFromDraft,
  validateShelfDraft,
  withShelfOwnerType,
} from "../features/shelves/shelfDraft";
import {
  confirmShelfDelete,
  localManageableShelfGroups,
  shelfEditBreadcrumbs,
  shelfNewBreadcrumbs,
  shouldLoadAllShelfGroups,
} from "../features/shelves/shelfLifecycle";
import { ShelfDetailsEditPageRegion } from "../features/shelves/regions/ShelfDetailsEditPageRegion";
import { ShelfEditAddBooksPageRegion } from "../features/shelves/regions/ShelfEditAddBooksPageRegion";
import { ShelfEditBooksPageRegion } from "../features/shelves/regions/ShelfEditBooksPageRegion";
import { ShelfEditTabsPageRegion } from "../features/shelves/regions/ShelfEditTabsPageRegion";
import { ShelfHeaderPageRegion } from "../features/shelves/regions/ShelfHeaderPageRegion";
import { LocalValidationError, idleMutationState } from "../shared/feedback/mutationState";

const baseUser: CurrentUser = {
  username: "reader", email: "", firstName: "", lastName: "", profileId: "profile",
  role: "reader", mustChangePassword: false, isOwner: false, isManager: false,
  isLibrarian: false, isReader: true, advancedLibraryGroupsEnabled: true,
  canAccessDjangoAdmin: false, bannerText: "", groups: [],
};
const publicGroup: LibraryGroup = {
  id: "public", name: "Common Room", description: "", isPublicGroup: true,
};
const personalShelf: ShelfSummary = {
  id: "shelf", name: "Favorites", description: "Reader picks", ownerType: "user",
  ownerUser: { profileId: "profile", username: "reader" }, ownerGroup: null,
  visibility: "listed", itemCount: 2, canEdit: true,
};
const groupShelf: ShelfSummary = {
  ...personalShelf, id: "group-shelf", ownerType: "group", ownerUser: null,
  ownerGroup: { id: "public", name: "Common Room", isPublicGroup: true },
  visibility: "private",
};

describe("Shelf lifecycle contracts", () => {
  it("normalizes create/edit drafts and sends only writable metadata", () => {
    expect(shelfDraftFromSummary(personalShelf)).toEqual({
      name: "Favorites", description: "Reader picks", ownerType: "user",
      ownerGroupId: "", visibility: "listed",
    });
    expect(createShelfInputFromDraft({
      ...emptyShelfDraft, name: " Group Shelf ", ownerType: "group",
      ownerGroupId: "group", visibility: "listed",
    })).toEqual({
      name: "Group Shelf", description: "", ownerType: "group",
      ownerGroupId: "group", visibility: "private",
    });
    expect(updateShelfInputFromDraft(shelfDraftFromSummary(groupShelf))).toEqual({
      name: "Favorites", description: "Reader picks",
    });
    expect(withShelfOwnerType({ ...emptyShelfDraft, ownerGroupId: "group" }, "user").ownerGroupId).toBe("");
    expect(shelfDraftsEqual(
      { ...emptyShelfDraft, name: " Shelf " },
      { ...emptyShelfDraft, name: "Shelf" },
    )).toBe(true);
  });

  it("rejects only meaningful local Shelf invariants", () => {
    for (const draft of [
      { ...emptyShelfDraft, name: "" },
      { ...emptyShelfDraft, name: "x".repeat(256) },
      { ...emptyShelfDraft, name: "Shelf", ownerType: "group" as const, ownerGroupId: "" },
      { ...emptyShelfDraft, name: "Shelf", ownerGroupId: "contradiction" },
    ]) expect(() => validateShelfDraft(draft)).toThrow(LocalValidationError);
    expect(() => validateShelfDraft({
      ...emptyShelfDraft,
      name: "Shelf",
      ownerType: "group",
      ownerGroupId: "unmanaged",
    }, ["managed"])).toThrow(LocalValidationError);
    expect(() => validateShelfDraft({ ...emptyShelfDraft, name: "Shelf" })).not.toThrow();
  });

  it("derives group-owner choices only from existing role and exact curator facts", () => {
    const curator = {
      ...baseUser,
      groups: [
        { id: "group", name: "Curated", isPublicGroup: false, isCurator: true },
        { id: "public", name: "Common Room", isPublicGroup: true, isCurator: false },
      ],
    };
    expect(localManageableShelfGroups(curator).map(({ id }) => id)).toEqual(["group"]);
    expect(shouldLoadAllShelfGroups(curator)).toBe(false);

    const simpleLibrarian = {
      ...baseUser, role: "librarian", isReader: false, isLibrarian: true,
      advancedLibraryGroupsEnabled: false,
      groups: [{ id: "public", name: "Common Room", isPublicGroup: true, isCurator: false }],
    };
    expect(localManageableShelfGroups(simpleLibrarian).map(({ id }) => id)).toEqual(["public"]);
    expect(shouldLoadAllShelfGroups({ ...simpleLibrarian, advancedLibraryGroupsEnabled: true })).toBe(true);
  });

  it("uses explicit lifecycle breadcrumbs and confirmation", () => {
    expect(shelfNewBreadcrumbs()).toEqual([
      { label: "Shelves", to: "/shelves", resetTrail: true },
      { label: "New Shelf" },
    ]);
    expect(shelfEditBreadcrumbs("shelf/id", "Favorites")).toEqual([
      { label: "Shelves", to: "/shelves", resetTrail: true },
      { label: "Favorites", to: "/shelves/shelf%2Fid" },
      { label: "Edit" },
    ]);
    const confirm = vi.fn(() => true);
    expect(confirmShelfDelete(confirm)).toBe(true);
    expect(confirm).toHaveBeenCalledOnce();
  });

  it("uses server canEdit for lifecycle affordances and keeps item controls out of Details", () => {
    const editableHeader = renderToStaticMarkup(<MemoryRouter><ShelfHeaderPageRegion
      shelf={personalShelf} loading={false} editPath="/shelves/shelf/edit" onRetry={vi.fn()}
    /></MemoryRouter>);
    const lockedHeader = renderToStaticMarkup(<MemoryRouter><ShelfHeaderPageRegion
      shelf={{ ...personalShelf, canEdit: false }} loading={false} editPath="/shelves/shelf/edit" onRetry={vi.fn()}
    /></MemoryRouter>);
    expect(editableHeader).toContain('href="/shelves/shelf/edit"');
    expect(lockedHeader).not.toContain('href="/shelves/shelf/edit"');

    const row = renderToStaticMarkup(<MemoryRouter><ShelfRowComponent
      shelf={personalShelf} detailPath="/shelves/shelf" previewBooks={[]}
      editPath="/shelves/shelf/edit"
    /></MemoryRouter>);
    expect(row).toContain('href="/shelves/shelf/edit"');

    const region = renderToStaticMarkup(<ShelfDetailsEditPageRegion
      mode="edit" shelf={groupShelf} draft={shelfDraftFromSummary(groupShelf)}
      groups={[publicGroup]} groupsLoading={false} mutation={idleMutationState}
      deleteMutation={idleMutationState} onChange={vi.fn()} onOwnerTypeChange={vi.fn()}
      onSubmit={vi.fn()} onCancel={vi.fn()} onDelete={vi.fn()}
    />);
    expect(region).not.toContain('id="shelf-visibility"');
    for (const absent of ["Add Book", "Remove Book", "Move up", "Move down"]) {
      expect(region).not.toContain(absent);
    }
  });

  it("exposes immediate add/remove item responsibilities without reorder controls", () => {
    const book = {
      id: "book", title: "Book", sortTitle: "Book", subtitle: "", authors: [], series: null,
      catalogTags: [], language: "", publisher: "", publishedYear: null, publishedMonth: null,
      publishedDay: null, publishedDatePrecision: "" as const, coverUrl: null, fileFormat: "EPUB",
    };
    const page = { count: 1, next: null, previous: null, items: [{
      id: "item", shelfId: "shelf", book, position: 0, addedBy: null,
    }] };
    const tabs = renderToStaticMarkup(<ShelfEditTabsPageRegion activeTab="details" onTabChange={vi.fn()} />);
    const books = renderToStaticMarkup(<MemoryRouter><ShelfEditBooksPageRegion
      shelfId="shelf" shelfName="Favorites" page={page} pageNumber={1} pageSize={20}
      loading={false} onRemove={vi.fn()} onPageChange={vi.fn()} onPageSizeChange={vi.fn()} onRetry={vi.fn()}
    /></MemoryRouter>);
    const candidates = renderToStaticMarkup(<MemoryRouter><ShelfEditAddBooksPageRegion
      shelfId="shelf" shelfName="Favorites" search="Book"
      page={{ count: 1, next: null, previous: null, items: [book] }} pageNumber={1} pageSize={20}
      loading={false} onSearchChange={vi.fn()} onSearch={vi.fn()} onAdd={vi.fn()}
      onPageChange={vi.fn()} onPageSizeChange={vi.fn()} onRetry={vi.fn()}
    /></MemoryRouter>);

    expect(tabs).toContain("Books");
    expect(tabs).toContain("Add Books");
    expect(books).toContain("Remove");
    expect(candidates).toContain("Add");
    for (const absent of ["Move up", "Move down", "Position"]) {
      expect(`${books}${candidates}`).not.toContain(absent);
    }
  });
});
