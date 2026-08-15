import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import type { CurrentUser, LibraryGroup, ShelfEditorItemsPage, ShelfSummary } from "@second-pass/spl-api";
import { breadcrumbNavigationState, readIncomingBreadcrumbTrail } from "../../../src/app/navigation/breadcrumbs";
import {
  authorizedShelfCreateGroupContext,
  canCreateShelfForGroup,
  readShelfCreateGroupContext,
  shelfCreateGroupReturnNavigationState,
  shelfCreateNavigationStateForGroup,
} from "../../../src/shared/shelves/shelfNavigation";
import {
  createShelfInputFromDraft,
  emptyShelfDraft,
  shelfDraftForGroupOwner,
  shelfDraftFromSummary,
  shelfDraftsEqual,
  updateShelfInputFromDraft,
  validateShelfDraft,
  withShelfOwnerType,
} from "../../../src/features/shelves/shelfDraft";
import {
  canPresentShelfGroupOwnerChoice,
  confirmShelfDelete,
  confirmUnavailableShelfItemRemoval,
  localManageableShelfGroups,
  shelfDetailNavigationStateFromEdit,
  shelfEditBreadcrumbs,
  shelfEditNavigationState,
  shelfNewBreadcrumbs,
  shouldLoadAllShelfGroups,
} from "../../../src/features/shelves/shelfLifecycle";
import { ShelfDetailsEditPageRegion } from "../../../src/features/shelves/regions/ShelfDetailsEditPageRegion";
import { ShelfEditAddBooksPageRegion } from "../../../src/features/shelves/edit/ShelfEditAddBooksPageRegion";
import {
  ShelfEditBooksPageRegion,
  ShelfPositionSelectComponent,
} from "../../../src/features/shelves/edit/ShelfEditBooksPageRegion";
import { ShelfEditTabsPageRegion } from "../../../src/features/shelves/edit/ShelfEditTabsPageRegion";
import { ShelfHeaderPageRegion } from "../../../src/features/shelves/detail/ShelfHeaderPageRegion";
import { LocalValidationError, idleMutationState } from "../../../src/shared/feedback/mutationState";

const baseUser: CurrentUser = {
  username: "reader", email: "", firstName: "", lastName: "", profileId: "profile",
  role: "reader", mustChangePassword: false, isOwner: false, isManager: false,
  isLibrarian: false, isReader: true, canAccessDjangoAdmin: false, groups: [],
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
    expect(localManageableShelfGroups(curator, true).map(({ id }) => id)).toEqual(["group"]);
    expect(shouldLoadAllShelfGroups(curator, true)).toBe(false);

    const simpleLibrarian = {
      ...baseUser, role: "librarian", isReader: false, isLibrarian: true,
      groups: [{ id: "public", name: "Common Room", isPublicGroup: true, isCurator: false }],
    };
    expect(localManageableShelfGroups(simpleLibrarian, false).map(({ id }) => id)).toEqual(["public"]);
    expect(shouldLoadAllShelfGroups(simpleLibrarian, true)).toBe(true);
    expect(canPresentShelfGroupOwnerChoice(publicGroup, false)).toBe(true);
    expect(canPresentShelfGroupOwnerChoice({ ...publicGroup, isPublicGroup: false }, false)).toBe(false);
    expect(canPresentShelfGroupOwnerChoice({ ...publicGroup, isPublicGroup: false }, true)).toBe(true);

    expect(canCreateShelfForGroup(simpleLibrarian, publicGroup)).toBe(true);
    expect(canCreateShelfForGroup(curator, publicGroup)).toBe(false);
    expect(canCreateShelfForGroup(curator, { ...publicGroup, id: "group", isPublicGroup: false })).toBe(true);
    expect(canCreateShelfForGroup(baseUser, { ...publicGroup, id: "group", isPublicGroup: false })).toBe(false);
  });

  it("carries exact Group ownership through Shelf create navigation", () => {
    const librarian = {
      ...baseUser,
      role: "librarian",
      isReader: false,
      isLibrarian: true,
    };
    const state = shelfCreateNavigationStateForGroup(publicGroup, "/groups/public?tab=shelves&page=2");
    const context = authorizedShelfCreateGroupContext(librarian, state)!;
    expect(readShelfCreateGroupContext(state)).toEqual(context);
    expect(context.groupId).toBe("public");
    expect(shelfDraftForGroupOwner(context.groupId)).toMatchObject({
      ownerType: "group",
      ownerGroupId: "public",
    });
    expect(createShelfInputFromDraft({
      ...shelfDraftForGroupOwner(context.groupId),
      name: "Group picks",
    })).toMatchObject({ ownerType: "group", ownerGroupId: "public" });
    expect(emptyShelfDraft).toMatchObject({ ownerType: "user", ownerGroupId: "" });

    const returnTrail = readIncomingBreadcrumbTrail(shelfCreateGroupReturnNavigationState(context))!;
    expect(context.returnTo).toBe("/groups/public?tab=shelves&page=2");
    expect(returnTrail.map(({ icon }) => icon)).toEqual(["group", "public-group"]);

    const successTrail = readIncomingBreadcrumbTrail(shelfEditNavigationState(state, groupShelf))!;
    expect(successTrail.map(({ icon }) => icon)).toEqual(["group", "public-group", "shelf", undefined]);
    expect(successTrail[1]?.to).toBe("/groups/public?tab=shelves&page=2");
  });

  it("rejects unauthorized or malformed Group Shelf create context", () => {
    const customGroup = { ...publicGroup, id: "custom", isPublicGroup: false };
    const state = shelfCreateNavigationStateForGroup(customGroup, "/groups/custom?tab=shelves");
    expect(authorizedShelfCreateGroupContext(baseUser, state)).toBeUndefined();
    expect(readShelfCreateGroupContext({
      ...state,
      shelfCreateGroupContext: {
        groupId: "custom",
        groupName: "Custom",
        isPublicGroup: false,
        returnTo: "/server",
      },
    })).toBeUndefined();
  });

  it("uses explicit lifecycle breadcrumbs and confirmation", () => {
    expect(shelfNewBreadcrumbs("group")).toEqual([
      { label: "Shelves", to: "/shelves", resetTrail: true, icon: "shelf" },
      { label: "Group Shelves", to: "/shelves?scope=group", icon: "group-shelf" },
      { label: "New Shelf" },
    ]);
    expect(shelfEditBreadcrumbs("shelf/id", "Favorites", "shared")).toEqual([
      { label: "Shelves", to: "/shelves", resetTrail: true, icon: "shelf" },
      { label: "Shared by Others", to: "/shelves?scope=shared", icon: "shared-shelf" },
      { label: "Favorites", to: "/shelves/shelf%2Fid", icon: "shelf" },
      { label: "Edit" },
    ]);
    const confirm = vi.fn(() => true);
    expect(confirmShelfDelete(confirm)).toBe(true);
    expect(confirm).toHaveBeenCalledOnce();
    expect(confirmUnavailableShelfItemRemoval(confirm)).toBe(true);
    expect(confirm).toHaveBeenCalledTimes(2);
  });

  it("preserves one Shelf scope crumb through detail and edit navigation", () => {
    const detailState = breadcrumbNavigationState([
      { label: "Shelves", to: "/shelves", resetTrail: true, icon: "shelf" },
      { label: "Group Shelves", to: "/shelves?scope=group", icon: "group-shelf" },
      { label: "Favorites", icon: "shelf" },
    ]);
    const editState = shelfEditNavigationState(detailState, groupShelf);
    const editTrail = readIncomingBreadcrumbTrail(editState)!;
    expect(editTrail.map(({ icon }) => icon).filter((icon) => icon === "group-shelf")).toHaveLength(1);
    expect(editTrail.at(-1)?.label).toBe("Edit");

    const returned = readIncomingBreadcrumbTrail(shelfDetailNavigationStateFromEdit(editState, groupShelf))!;
    expect(returned.map(({ label }) => label)).toEqual(["Shelves", "Group Shelves", "Favorites"]);
    expect(returned[1]?.to).toBe("/shelves?scope=group");
  });

  it("builds truthful lifecycle fallbacks when incoming state is absent", () => {
    const groupEdit = readIncomingBreadcrumbTrail(shelfEditNavigationState(undefined, groupShelf))!;
    const sharedDetail = readIncomingBreadcrumbTrail(shelfDetailNavigationStateFromEdit(
      undefined,
      { ...personalShelf, canEdit: false },
    ))!;
    expect(groupEdit[1]).toEqual({
      label: "Group Shelves", to: "/shelves?scope=group", icon: "group-shelf",
    });
    expect(sharedDetail[1]).toEqual({
      label: "Shared by Others", to: "/shelves?scope=shared", icon: "shared-shelf",
    });
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

  it("renders editor inventory controls while keeping unavailable rows locked", () => {
    const book = {
      id: "book-a", title: "Book A", sortTitle: "Book A", subtitle: "", authors: [], series: null,
      catalogTags: [], language: "", publisher: "", publishedYear: null, publishedMonth: null,
      publishedDay: null, publishedDatePrecision: "" as const, coverUrl: null, fileFormat: "EPUB",
    };
    const page: ShelfEditorItemsPage = {
      count: 3,
      visibleItemCount: 2,
      unavailableItemCount: 1,
      next: null,
      previous: null,
      items: [
        { id: "item-a", shelfId: "shelf", book, position: 0, unavailable: false, addedBy: null },
        { id: "item-hidden", shelfId: "shelf", book: null, position: 1, unavailable: true, addedBy: null },
        {
          id: "item-c", shelfId: "shelf", position: 2, unavailable: false, addedBy: null,
          book: { ...book, id: "book-c", title: "Book C", sortTitle: "Book C" },
        },
      ],
    };
    const tabs = renderToStaticMarkup(<ShelfEditTabsPageRegion activeTab="details" onTabChange={vi.fn()} />);
    const books = renderToStaticMarkup(<MemoryRouter><ShelfEditBooksPageRegion
      shelfId="shelf" shelfName="Favorites" scope="personal" page={page} pageNumber={1} pageSize={20}
      loading={false} onMove={vi.fn()} onMoveTo={vi.fn()} onRemove={vi.fn()} onPageChange={vi.fn()} onPageSizeChange={vi.fn()} onRetry={vi.fn()}
    /></MemoryRouter>);
    const candidates = renderToStaticMarkup(<MemoryRouter><ShelfEditAddBooksPageRegion
      shelfId="shelf" shelfName="Favorites" scope="personal" search="Book"
      page={{ count: 1, next: null, previous: null, items: [book] }} pageNumber={1} pageSize={20}
      loading={false} onSearchChange={vi.fn()} onSearch={vi.fn()} onAdd={vi.fn()}
      onPageChange={vi.fn()} onPageSizeChange={vi.fn()} onRetry={vi.fn()}
    /></MemoryRouter>);

    expect(tabs).toContain("Books");
    expect(tabs).toContain("Add Books");
    expect(tabs).toContain('role="tablist"');
    expect(tabs).toContain('aria-selected="true"');
    expect(books).toContain("Unavailable item");
    expect(books).toContain('aria-label="Remove unavailable item"');
    expect(books).not.toContain("hidden_book_id");
    expect(books).toContain('aria-label="Move Book A up"');
    expect(books).toContain('aria-label="Move Book A down"');
    expect(books).toContain('aria-label="Move Book C up"');
    expect(books).toContain('aria-label="Move Book C down"');
    expect(books).toMatch(/aria-label="Move Book A up"[^>]*disabled/);
    expect(books).not.toMatch(/aria-label="Move Book A down"[^>]*disabled/);
    expect(books).not.toMatch(/aria-label="Move Book C up"[^>]*disabled/);
    expect(books).toMatch(/aria-label="Move Book C down"[^>]*disabled/);
    expect(books).toContain("Move To");
    expect(books).toMatch(/aria-label="Move Book A to position"[^>]*disabled/);
    expect(candidates).toContain("Add");
  });

  it("renders one-based Move To options and reports the selected zero-based position", () => {
    const onChange = vi.fn();
    const control = ShelfPositionSelectComponent({
      bookTitle: "Book A",
      position: 1,
      positionCount: 4,
      disabled: false,
      onChange,
    });
    const markup = renderToStaticMarkup(control);
    const select = control.props.children[1];

    expect(markup).toContain("Move To");
    expect(markup).toContain('<option value="0">1</option>');
    expect(markup).toContain('<option value="1" disabled="" selected="">2</option>');
    expect(markup).toContain('<option value="3">4</option>');

    select.props.onChange({ target: { value: "3" } });
    expect(onChange).toHaveBeenCalledWith(3);
  });

  it("keeps Move To controlled by the authoritative Shelf page during pending and failure states", () => {
    const book = {
      id: "book-a", title: "Book A", sortTitle: "Book A", subtitle: "", authors: [], series: null,
      catalogTags: [], language: "", publisher: "", publishedYear: null, publishedMonth: null,
      publishedDay: null, publishedDatePrecision: "" as const, coverUrl: null, fileFormat: "EPUB",
    };
    const page: ShelfEditorItemsPage = {
      count: 2, visibleItemCount: 2, unavailableItemCount: 0, next: null, previous: null,
      items: [
        { id: "item-a", shelfId: "shelf", book, position: 0, unavailable: false, addedBy: null },
        { id: "item-b", shelfId: "shelf", book: { ...book, id: "book-b", title: "Book B" }, position: 1, unavailable: false, addedBy: null },
      ],
    };
    const renderBooks = (currentPage: ShelfEditorItemsPage, props: { pendingItemId?: string; error?: Error } = {}) => renderToStaticMarkup(
      <MemoryRouter><ShelfEditBooksPageRegion
        shelfId="shelf" shelfName="Favorites" scope="personal" page={currentPage} pageNumber={1} pageSize={20}
        loading={false} {...props} onMove={vi.fn()} onMoveTo={vi.fn()} onRemove={vi.fn()}
        onPageChange={vi.fn()} onPageSizeChange={vi.fn()} onRetry={vi.fn()}
      /></MemoryRouter>,
    );

    const pending = renderBooks(page, { pendingItemId: "item-a" });
    const failed = renderBooks(page, { error: new Error("Move failed.") });
    const authoritative = renderBooks({ ...page, items: [
      { ...page.items[1], position: 0 },
      { ...page.items[0], position: 1 },
    ] });

    expect(pending).toMatch(/aria-label="Move Book A to position"[^>]*disabled/);
    expect(failed).toContain("Move failed.");
    expect(failed).toMatch(/aria-label="Move Book A to position"[^>]*><option value="0" disabled="" selected="">1<\/option>/);
    expect(authoritative.indexOf("Book B")).toBeLessThan(authoritative.indexOf("Book A"));
  });

  it("disables Shelf Edit tab activation while an immediate item mutation is pending", () => {
    const markup = renderToStaticMarkup(<ShelfEditTabsPageRegion
      activeTab="books"
      disabled
      onTabChange={vi.fn()}
    />);
    const buttons = markup.match(/<button\b[^>]*>/g) ?? [];
    expect(buttons).toHaveLength(3);
    expect(buttons.every((button) => button.includes("disabled"))).toBe(true);
  });
});

