import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import type { CurrentUser, LibraryGroup } from "@second-pass/spl-api";
import {
  createGroupInputFromDraft,
  groupDraftFromGroup,
  groupDraftsEqual,
  updateGroupInputFromDraft,
  validateGroupDraft,
} from "../../../src/features/groups/groupDraft";
import { confirmGroupBookRemoval, confirmGroupMemberRemoval } from "../../../src/features/groups/edit/groupBookMutation";
import { confirmGroupDelete } from "../../../src/features/groups/edit/groupDelete";
import {
  canDeleteGroup,
  canManageGroup,
  canMutateGroupBooks,
  canMutateGroupMembers,
  canCreateGroupMetadata,
  groupMetadataAuthority,
} from "../../../src/features/groups/groupMetadataAuthority";
import {
  groupEditBreadcrumbFallback,
  groupEditPath,
  groupNewBreadcrumbs,
} from "../../../src/features/groups/groupsBreadcrumbs";
import { GroupMetadataFormPageRegion } from "../../../src/features/groups/regions/GroupMetadataFormPageRegion";
import { GroupBookCandidatesPageRegion } from "../../../src/features/groups/edit/GroupBookCandidatesPageRegion";
import { GroupBooksEditPageRegion } from "../../../src/features/groups/edit/GroupBooksEditPageRegion";
import { GroupEditTabsPageRegion } from "../../../src/features/groups/edit/GroupEditTabsPageRegion";
import { GroupDangerZonePageRegion } from "../../../src/features/groups/edit/GroupDangerZonePageRegion";
import { GroupMemberCandidatesPageRegion } from "../../../src/features/groups/edit/GroupMemberCandidatesPageRegion";
import { GroupMembersEditPageRegion } from "../../../src/features/groups/edit/GroupMembersEditPageRegion";
import { GroupPublicDetailsPageRegion } from "../../../src/features/groups/edit/GroupPublicDetailsPageRegion";
import { MemoryRouter } from "react-router";

const baseUser: CurrentUser = {
  username: "reader", email: "", firstName: "", lastName: "", profileId: "profile",
  role: "reader", mustChangePassword: false, isOwner: false, isManager: false,
  isLibrarian: false, isReader: true, canAccessDjangoAdmin: false, groups: [],
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

    expect(canCreateGroupMetadata(manager, true)).toBe(true);
    expect(canCreateGroupMetadata(owner, true)).toBe(true);
    expect(canCreateGroupMetadata(librarian, true)).toBe(false);
    expect(groupMetadataAuthority(manager, customGroup, true)).toBe("full");
    expect(groupMetadataAuthority(owner, customGroup, true)).toBe("full");
    expect(groupMetadataAuthority(librarian, customGroup, true)).toBe("description");
    expect(groupMetadataAuthority(curator, customGroup, true)).toBe("description");
    expect(groupMetadataAuthority(baseUser, customGroup, true)).toBe("none");
    expect(groupMetadataAuthority(manager, publicGroup, true)).toBe("none");
    expect(groupMetadataAuthority(manager, customGroup, false)).toBe("none");
    expect(canMutateGroupBooks(manager, customGroup, true)).toBe(true);
    expect(canMutateGroupBooks(owner, customGroup, true)).toBe(true);
    expect(canMutateGroupBooks(librarian, customGroup, true)).toBe(true);
    expect(canMutateGroupBooks(curator, customGroup, true)).toBe(true);
    expect(canMutateGroupBooks(baseUser, customGroup, true)).toBe(false);
    expect(canMutateGroupBooks(librarian, publicGroup, true)).toBe(true);
    expect(canMutateGroupBooks(curator, publicGroup, true)).toBe(false);
    expect(canMutateGroupBooks(manager, customGroup, false)).toBe(false);
    expect(canMutateGroupMembers(manager, true)).toBe(true);
    expect(canMutateGroupMembers(owner, true)).toBe(true);
    expect(canMutateGroupMembers(librarian, true)).toBe(false);
    expect(canMutateGroupMembers(curator, true)).toBe(false);
    expect(canDeleteGroup(manager, customGroup, true)).toBe(true);
    expect(canDeleteGroup(owner, customGroup, true)).toBe(true);
    expect(canDeleteGroup(librarian, customGroup, true)).toBe(false);
    expect(canDeleteGroup(curator, customGroup, true)).toBe(false);
    expect(canDeleteGroup(manager, publicGroup, true)).toBe(false);
    expect(canManageGroup(manager, customGroup, true)).toBe(true);
    expect(canManageGroup(librarian, customGroup, true)).toBe(true);
    expect(canManageGroup(curator, customGroup, true)).toBe(true);
    expect(canManageGroup(librarian, publicGroup, true)).toBe(true);
    expect(canManageGroup(manager, publicGroup, true)).toBe(true);
    expect(canManageGroup(baseUser, customGroup, true)).toBe(false);
    expect(canManageGroup(baseUser, publicGroup, true)).toBe(false);
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
      { label: "Groups", to: "/groups", resetTrail: true, icon: "group" },
      { label: "New Group" },
    ]);
    expect(groupEditBreadcrumbFallback("group/id", "Readers")).toEqual([
      { label: "Groups", to: "/groups", resetTrail: true, icon: "group" },
      { label: "Readers", to: "/groups/group%2Fid", icon: "group" },
      { label: "Edit" },
    ]);
  });

  it("keeps every predefined Group management section visible", () => {
    const markup = renderToStaticMarkup(<GroupEditTabsPageRegion
      activeTab="details"
      onTabChange={vi.fn()}
    />);
    expect(markup).toContain('role="tablist"');
    for (const label of ["Details", "Books", "Add Books", "Members"]) {
      expect(markup).toContain(label);
    }
  });

  it("disables all Group Edit tabs while an immediate mutation is pending", () => {
    const markup = renderToStaticMarkup(<GroupEditTabsPageRegion
      activeTab="books"
      disabled
      onTabChange={vi.fn()}
    />);
    const buttons = markup.match(/<button\b[^>]*>/g) ?? [];
    expect(buttons.length).toBeGreaterThan(0);
    expect(buttons.every((button) => button.includes("disabled"))).toBe(true);
  });

  it("renders Public Details as read-only policy context rather than an error", () => {
    const markup = renderToStaticMarkup(<GroupPublicDetailsPageRegion group={publicGroup} />);
    expect(markup).toContain('aria-label="Public group: Readers"');
    expect(markup).toContain("Server Settings");
    expect(markup).not.toContain('role="alert"');
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

    expect(custom).toContain('aria-label="User reader"');
    expect(custom).not.toContain("@reader");
    expect(custom).toContain("Curator");
    expect(custom).toContain("Remove curator");
    expect(custom).toContain("Membership update failed.");
    expect(custom).not.toContain("Global role");
    expect(custom).not.toContain(">Member<");
    expect(publicGroupMembers).not.toContain("Remove curator");
    expect(publicGroupMembers).not.toContain("Make curator");
    expect(choices).toContain('aria-label="User new-reader"');
    expect(choices).not.toContain("@new-reader");
    expect(blank).not.toContain("new-reader");
  });

  it("confirms membership removal without implying user deletion", () => {
    const deny = vi.fn(() => false);
    expect(confirmGroupMemberRemoval(deny)).toBe(false);
    expect(deny).toHaveBeenCalledWith("Remove this member from the group?");
  });

  it("renders Delete only through an explicit custom-Group danger contract", () => {
    const danger = renderToStaticMarkup(<GroupDangerZonePageRegion
      state={{ pending: false, error: new Error("Delete failed.") }}
      onDelete={vi.fn()}
    />);
    expect(danger).toContain("Delete Group");
    expect(danger).toContain("Delete failed.");
    expect(danger).toContain("Users, Books, and files are not deleted.");

    const disabledDanger = renderToStaticMarkup(<GroupDangerZonePageRegion
      state={{ pending: false }}
      controlsDisabled
      onDelete={vi.fn()}
    />);
    expect(disabledDanger).toContain("disabled");

    const reject = vi.fn((_message: string) => false);
    expect(confirmGroupDelete(reject)).toBe(false);
    const message = reject.mock.calls[0]?.[0] ?? "";
    for (const meaning of ["memberships", "book assignments", "shelves owned", "Public/Common Room", "not deleted"]) {
      expect(message).toMatch(new RegExp(meaning, "i"));
    }
  });
});

