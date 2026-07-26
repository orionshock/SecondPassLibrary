import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import type { CurrentUser, LibraryGroup } from "@second-pass/spl-api";
import {
  createGroupInputFromDraft,
  groupDraftFromGroup,
  groupDraftsEqual,
  updateGroupInputFromDraft,
  validateGroupDraft,
} from "../features/groups/groupDraft";
import { confirmGroupBookRemoval, confirmGroupMemberRemoval } from "../features/groups/groupBookMutation";
import {
  canMutateGroupBooks,
  canMutateGroupMembers,
  canCreateGroupMetadata,
  groupMetadataAuthority,
} from "../features/groups/groupMetadataAuthority";
import {
  groupEditBreadcrumbFallback,
  groupEditPath,
  groupNewBreadcrumbs,
} from "../features/groups/groupsBreadcrumbs";
import { GroupMetadataFormPageRegion } from "../features/groups/regions/GroupMetadataFormPageRegion";
import { GroupBookCandidatesPageRegion } from "../features/groups/regions/GroupBookCandidatesPageRegion";
import { GroupBooksEditPageRegion } from "../features/groups/regions/GroupBooksEditPageRegion";
import { GroupEditTabsPageRegion } from "../features/groups/regions/GroupEditTabsPageRegion";
import { GroupMemberCandidatesPageRegion } from "../features/groups/regions/GroupMemberCandidatesPageRegion";
import { GroupMembersEditPageRegion } from "../features/groups/regions/GroupMembersEditPageRegion";
import { MemoryRouter } from "react-router-dom";

const baseUser: CurrentUser = {
  username: "reader", email: "", firstName: "", lastName: "", profileId: "profile",
  role: "reader", mustChangePassword: false, isOwner: false, isManager: false,
  isLibrarian: false, isReader: true, advancedLibraryGroupsEnabled: true,
  canAccessDjangoAdmin: false, bannerText: "", groups: [],
};
const customGroup: LibraryGroup = {
  id: "group/id", name: "Readers", description: "Description", isPublicGroup: false,
};
const publicGroup: LibraryGroup = { ...customGroup, id: "public", isPublicGroup: true };

describe("Group metadata lifecycle contracts", () => {
  it("derives operation-specific metadata authority from role and exact membership facts", () => {
    const manager = { ...baseUser, role: "manager", isManager: true, isReader: false };
    const owner = { ...manager, isOwner: true, isManager: false };
    const librarian = { ...baseUser, role: "librarian", isLibrarian: true, isReader: false };
    const curator = {
      ...baseUser,
      groups: [{ id: customGroup.id, name: customGroup.name, isPublicGroup: false, isCurator: true }],
    };

    expect(canCreateGroupMetadata(manager)).toBe(true);
    expect(canCreateGroupMetadata(owner)).toBe(true);
    expect(canCreateGroupMetadata(librarian)).toBe(false);
    expect(groupMetadataAuthority(manager, customGroup)).toBe("full");
    expect(groupMetadataAuthority(owner, customGroup)).toBe("full");
    expect(groupMetadataAuthority(librarian, customGroup)).toBe("description");
    expect(groupMetadataAuthority(curator, customGroup)).toBe("description");
    expect(groupMetadataAuthority(baseUser, customGroup)).toBe("none");
    expect(groupMetadataAuthority(manager, publicGroup)).toBe("none");
    expect(groupMetadataAuthority({ ...manager, advancedLibraryGroupsEnabled: false }, customGroup)).toBe("none");
    expect(canMutateGroupBooks(manager, customGroup)).toBe(true);
    expect(canMutateGroupBooks(owner, customGroup)).toBe(true);
    expect(canMutateGroupBooks(librarian, customGroup)).toBe(true);
    expect(canMutateGroupBooks(curator, customGroup)).toBe(true);
    expect(canMutateGroupBooks(baseUser, customGroup)).toBe(false);
    expect(canMutateGroupBooks(librarian, publicGroup)).toBe(true);
    expect(canMutateGroupBooks(curator, publicGroup)).toBe(false);
    expect(canMutateGroupBooks({ ...manager, advancedLibraryGroupsEnabled: false }, customGroup)).toBe(false);
    expect(canMutateGroupMembers(manager)).toBe(true);
    expect(canMutateGroupMembers(owner)).toBe(true);
    expect(canMutateGroupMembers(librarian)).toBe(false);
    expect(canMutateGroupMembers(curator)).toBe(false);
  });

  it("normalizes dirty comparison and mutation inputs while allowing duplicate names", () => {
    const baseline = groupDraftFromGroup(customGroup);
    expect(groupDraftsEqual({ ...baseline, name: "  Readers  " }, baseline)).toBe(true);
    expect(groupDraftsEqual({ ...baseline, description: "Changed" }, baseline)).toBe(false);
    expect(createGroupInputFromDraft({ name: "  Readers  ", description: "Same name allowed" })).toEqual({
      name: "Readers", description: "Same name allowed",
    });
    expect(updateGroupInputFromDraft({ name: "Readers", description: "Changed" })).toEqual({
      name: "Readers", description: "Changed",
    });
  });

  it("rejects only missing or overlong names locally", () => {
    expect(() => validateGroupDraft({ name: " ", description: "" })).toThrowError(/highlighted/i);
    expect(() => validateGroupDraft({ name: "x".repeat(256), description: "" })).toThrowError(/highlighted/i);
    expect(() => validateGroupDraft({ name: "Readers", description: "" })).not.toThrow();
  });

  it("keeps name non-editable for description-only authority", () => {
    const markup = renderToStaticMarkup(<GroupMetadataFormPageRegion
      mode="edit"
      draft={{ name: "Readers", description: "Description" }}
      nameEditable={false}
      state={{ pending: false }}
      onChange={vi.fn()}
      onSubmit={vi.fn()}
      onCancel={vi.fn()}
    />);
    expect(markup).toContain('id="group-name"');
    expect(markup).toContain("disabled");
    expect(markup).toContain('id="group-description"');
  });

  it("builds canonical create/edit routes and fallback breadcrumbs", () => {
    expect(groupEditPath("group/id")).toBe("/groups/group%2Fid/edit");
    expect(groupNewBreadcrumbs()).toEqual([
      { label: "Groups", to: "/groups", resetTrail: true },
      { label: "New Group" },
    ]);
    expect(groupEditBreadcrumbFallback("group/id", "Readers")).toEqual([
      { label: "Groups", to: "/groups", resetTrail: true },
      { label: "Readers", to: "/groups/group%2Fid" },
      { label: "Edit" },
    ]);
  });

  it("shows Book mutation tabs only with exact curation authority", () => {
    const editable = renderToStaticMarkup(<GroupEditTabsPageRegion
      activeTab="details"
      canMutateBooks
      canMutateMembers
      onTabChange={vi.fn()}
    />);
    const readOnly = renderToStaticMarkup(<GroupEditTabsPageRegion
      activeTab="details"
      canMutateBooks={false}
      canMutateMembers={false}
      onTabChange={vi.fn()}
    />);
    expect(editable).toContain("Books");
    expect(editable).toContain("Add Books");
    expect(editable).toContain("Members");
    expect(readOnly).not.toContain("Books");
    expect(readOnly).not.toContain("Members");
  });

  it("keeps assigned rows visible with persistent removal errors and exposes explicit candidate actions", () => {
    const book = {
      id: "book", title: "Visible Book", sortTitle: "Visible Book", subtitle: "", authors: [],
      series: null, catalogTags: [], language: "", publisher: "", publishedYear: null,
      publishedMonth: null, publishedDay: null, publishedDatePrecision: "", coverUrl: null,
      fileFormat: "epub",
    };
    const page = { items: [book], count: 1, next: null, previous: null };
    const assigned = renderToStaticMarkup(<MemoryRouter><GroupBooksEditPageRegion
      groupId="group" groupName="Readers" page={page} pageNumber={1} pageSize={20}
      loading={false} error={new Error("Group shelf cleanup failed.")} onRemove={vi.fn()}
      onPageChange={vi.fn()} onPageSizeChange={vi.fn()} onRetry={vi.fn()}
    /></MemoryRouter>);
    const candidates = renderToStaticMarkup(<MemoryRouter><GroupBookCandidatesPageRegion
      groupId="group" groupName="Readers" search="Visible" page={page} pageNumber={1} pageSize={20}
      loading={false} onSearchChange={vi.fn()} onSearch={vi.fn()} onAdd={vi.fn()}
      onPageChange={vi.fn()} onPageSizeChange={vi.fn()} onRetry={vi.fn()}
    /></MemoryRouter>);
    const blankCandidates = renderToStaticMarkup(<MemoryRouter><GroupBookCandidatesPageRegion
      groupId="group" groupName="Readers" search="" pageNumber={1} pageSize={20}
      loading={false} onSearchChange={vi.fn()} onSearch={vi.fn()} onAdd={vi.fn()}
      onPageChange={vi.fn()} onPageSizeChange={vi.fn()} onRetry={vi.fn()}
    /></MemoryRouter>);

    expect(assigned).toContain("Group shelf cleanup failed.");
    expect(assigned).toContain("Visible Book");
    expect(assigned).toContain('aria-label="Remove Visible Book from group"');
    expect(candidates).toContain(">Add<");
    expect(blankCandidates).not.toContain("Visible Book");
  });

  it("confirms the Group-owned Shelf impact before Book removal", () => {
    const deny = vi.fn(() => false);
    expect(confirmGroupBookRemoval(deny)).toBe(false);
    expect(deny).toHaveBeenCalledWith(expect.stringMatching(/also be removed from shelves owned by this group/i));
  });

  it("renders member mutation facts without global role controls", () => {
    const membership = { user: { profileId: "profile", username: "reader" }, isCurator: true };
    const page = { items: [membership], count: 1, next: null, previous: null };
    const custom = renderToStaticMarkup(<GroupMembersEditPageRegion
      page={page} pageNumber={1} pageSize={20} isPublicGroup={false} loading={false}
      error={new Error("Membership update failed.")} onToggleCurator={vi.fn()} onRemove={vi.fn()}
      onPageChange={vi.fn()} onPageSizeChange={vi.fn()} onRetry={vi.fn()}
    />);
    const publicGroupMembers = renderToStaticMarkup(<GroupMembersEditPageRegion
      page={page} pageNumber={1} pageSize={20} isPublicGroup loading={false}
      onToggleCurator={vi.fn()} onRemove={vi.fn()} onPageChange={vi.fn()}
      onPageSizeChange={vi.fn()} onRetry={vi.fn()}
    />);
    const choices = renderToStaticMarkup(<GroupMemberCandidatesPageRegion
      search="read" page={{ items: [{ profileId: "new", username: "new-reader" }], count: 1, next: null, previous: null }}
      pageNumber={1} pageSize={20} loading={false} onSearchChange={vi.fn()} onSearch={vi.fn()}
      onAdd={vi.fn()} onPageChange={vi.fn()} onPageSizeChange={vi.fn()} onRetry={vi.fn()}
    />);
    const blank = renderToStaticMarkup(<GroupMemberCandidatesPageRegion
      search="" pageNumber={1} pageSize={20} loading={false} onSearchChange={vi.fn()}
      onSearch={vi.fn()} onAdd={vi.fn()} onPageChange={vi.fn()} onPageSizeChange={vi.fn()} onRetry={vi.fn()}
    />);

    expect(custom).toContain("&lt;@reader&gt;");
    expect(custom).toContain("Curator");
    expect(custom).toContain("Remove curator");
    expect(custom).toContain("Membership update failed.");
    expect(custom).not.toContain("Global role");
    expect(custom).not.toContain(">Member<");
    expect(publicGroupMembers).not.toContain("Remove curator");
    expect(publicGroupMembers).not.toContain("Make curator");
    expect(choices).toContain("&lt;@new-reader&gt;");
    expect(blank).not.toContain("new-reader");
  });

  it("confirms membership removal without implying user deletion", () => {
    const deny = vi.fn(() => false);
    expect(confirmGroupMemberRemoval(deny)).toBe(false);
    expect(deny).toHaveBeenCalledWith("Remove this member from the group?");
  });
});
