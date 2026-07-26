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
import {
  canCreateGroupMetadata,
  groupMetadataAuthority,
} from "../features/groups/groupMetadataAuthority";
import {
  groupEditBreadcrumbFallback,
  groupEditPath,
  groupNewBreadcrumbs,
} from "../features/groups/groupsBreadcrumbs";
import { GroupMetadataFormPageRegion } from "../features/groups/regions/GroupMetadataFormPageRegion";

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
});
