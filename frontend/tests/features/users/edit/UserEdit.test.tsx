import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { ApiError, type CurrentUser, type ManagedPasswordResetResult, type ManagedUser } from "@second-pass/spl-api";
import { UserDetailsPageRegion } from "../../../../src/features/users/edit/UserDetailsPageRegion";
import { canRemoveMembership, curatorValueForGroup, UserGroupMembershipsPageRegion } from "../../../../src/features/users/edit/UserGroupMembershipsPageRegion";
import { UserPasswordPageRegion } from "../../../../src/features/users/edit/UserPasswordPageRegion";
import { shouldShowManagedGroupMemberships } from "../../../../src/features/users/edit/UserEditOrchestrator";
import { userEditDraftFromUser, userEditDraftReducer } from "../../../../src/features/users/edit/userEditForm";
import { editableUserRoles } from "../../../../src/features/users/userCreateRoles";
import { usersEditBreadcrumbFallbackFor, usersEditBreadcrumbTrail } from "../../../../src/features/users/usersBreadcrumbs";
import { confirmGroupMembershipRemoval, confirmManagedPasswordReset } from "../../../../src/features/users/edit/userEditConfirmations";

const target: ManagedUser = {
  id: "target", username: "reader", firstName: "Read", lastName: "Er", email: "reader@example.test", role: "reader",
  isOwner: false, isActive: true, dateJoined: "2026-01-01T00:00:00Z", lastLogin: null, mustChangePassword: false,
  groups: [{ id: "public", name: "Common Room", isPublicGroup: true, isCurator: false }, { id: "custom", name: "Book Club", isPublicGroup: false, isCurator: true }],
};
const owner: CurrentUser = { username: "owner", email: "", firstName: "", lastName: "", profileId: "owner", role: "manager", mustChangePassword: false, isOwner: true, isManager: false, isLibrarian: false, isReader: false, canAccessDjangoAdmin: false, groups: [] };
const manager: CurrentUser = { ...owner, username: "manager", profileId: "manager", isOwner: false, isManager: true };

describe("User Edit", () => {
  it("uses canonical identity breadcrumbs and permission-aware capitalized roles", () => {
    expect(usersEditBreadcrumbFallbackFor("reader")).toEqual([{ label: "Users", to: "/users", resetTrail: true, icon: "user" }, { label: "reader", icon: "user" }, { label: "Edit" }]);
    expect(usersEditBreadcrumbTrail("reader")).toEqual(usersEditBreadcrumbFallbackFor("reader"));
    expect(editableUserRoles(owner, target)).toEqual(["manager", "librarian", "reader"]);
    expect(editableUserRoles(manager, target)).toEqual(["librarian", "reader"]);
    expect(editableUserRoles(manager, { ...target, role: "manager" })).toEqual([]);
  });

  it("renders editable status and preserves local cancel/reset behavior", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><UserDetailsPageRegion user={target} roles={editableUserRoles(owner, target)} canEdit canChangeActive state={{ pending: false, message: "Saved." }} onSave={vi.fn()} onClearStatus={vi.fn()} /></MemoryRouter>);
    expect(markup).toContain('<option value="active" selected="">Active</option>');
    expect(markup).toContain('<option value="inactive">Inactive</option>');
    expect(markup).not.toContain('>true<');
    expect(markup).toContain('>Manager<');
    expect(markup).toContain('>Librarian<');
    const changed = userEditDraftReducer(userEditDraftFromUser(target), { type: "change", field: "firstName", value: "Changed" });
    expect(userEditDraftReducer(changed, { type: "reset", value: userEditDraftFromUser(target) }).firstName).toBe("Read");
  });

  it("renders field and action errors", () => {
    const error = new ApiError("Invalid user.", 400, { fields: { email: ["Invalid email."] } });
    const markup = renderToStaticMarkup(<MemoryRouter><UserDetailsPageRegion user={target} roles={["reader"]} canEdit canChangeActive state={{ pending: false, error }} onSave={vi.fn()} onClearStatus={vi.fn()} /></MemoryRouter>);
    expect(markup).toContain("Invalid email.");
    expect(markup).toContain('role="alert"');
  });

  it("requires reset confirmation and renders a read-only one-time password result", () => {
    expect(confirmManagedPasswordReset(vi.fn(() => false))).toBe(false);
    const result: ManagedPasswordResetResult = { username: "reader", temporaryPassword: "one-time", message: "show once" };
    const markup = renderToStaticMarkup(<MemoryRouter><UserPasswordPageRegion mustChangePassword canManage requirementState={{ pending: false }} resetState={{ pending: false, message: "Password reset." }} resetResult={result} onRequirementChange={vi.fn()} onReset={vi.fn()} /></MemoryRouter>);
    expect(markup).toContain('readOnly=""');
    expect(markup).toContain("Username: reader");
    expect(markup).toContain('aria-label="User reader"');
    expect(markup).toContain("Password: one-time");
    expect(markup).toContain("Require password change on next login");
  });

  it("renders removable Public membership with its public badge and curator help", () => {
    expect(confirmGroupMembershipRemoval("Book Club", vi.fn(() => false))).toBe(false);
    const markup = renderToStaticMarkup(<MemoryRouter><UserGroupMembershipsPageRegion memberships={target.groups} assignableGroups={[{ id: "new", name: "New Group", isPublicGroup: false }]} state={{ pending: false }} onAdd={vi.fn()} onRemove={vi.fn()} onCuratorChange={vi.fn()} /></MemoryRouter>);
    expect(markup).toContain("Public Group");
    expect(markup).toContain('aria-label="Public group: Common Room"');
    expect(markup).toContain('aria-label="Group: Book Club"');
    expect(markup).toContain("Only Librarians/Managers may Curate the Public Group");
    expect(markup).toContain('aria-label="Remove Common Room"');
    expect(markup).toContain('aria-label="Remove Book Club"');
    expect(markup).toContain("Add to group");
  });

  it("disables sole Public removal but keeps a sole custom membership removable", () => {
    const publicGroup = target.groups[0]!;
    const customGroup = target.groups[1]!;
    const render = (membership: typeof publicGroup) => renderToStaticMarkup(<MemoryRouter><UserGroupMembershipsPageRegion memberships={[membership]} assignableGroups={[]} state={{ pending: false }} onAdd={vi.fn()} onRemove={vi.fn()} onCuratorChange={vi.fn()} /></MemoryRouter>);

    const publicMarkup = render(publicGroup);
    expect(canRemoveMembership(publicGroup, 1)).toBe(false);
    expect(publicMarkup).toContain('disabled=""');
    expect(publicMarkup).not.toContain("Fallback while sole group");
    expect(publicMarkup).not.toContain("Available to everyone");
    expect(publicMarkup).not.toContain('type="checkbox"');
    expect(canRemoveMembership(customGroup, 1)).toBe(true);
    expect(render(customGroup)).toContain('aria-label="Remove Book Club"');
  });

  it("allows Public in Add-to-group and suppresses curator assignment", () => {
    const publicGroup = { id: "public", name: "Common Room", isPublicGroup: true } as const;
    const markup = renderToStaticMarkup(<MemoryRouter><UserGroupMembershipsPageRegion memberships={[]} assignableGroups={[publicGroup]} state={{ pending: false }} onAdd={vi.fn()} onRemove={vi.fn()} onCuratorChange={vi.fn()} /></MemoryRouter>);

    expect(markup).toContain('<option value="public" selected="">Common Room</option>');
    expect(markup).toContain("Public membership cannot be curator.");
    expect(markup).not.toContain("Grant curator access");
    expect(curatorValueForGroup(publicGroup, true)).toBe(false);
    expect(curatorValueForGroup({ ...publicGroup, isPublicGroup: false }, true)).toBe(true);
  });

  it("shows advanced group management to Managers regardless of target account-edit authority", () => {
    expect(shouldShowManagedGroupMemberships(true, manager)).toBe(true);
    expect(shouldShowManagedGroupMemberships(true, owner)).toBe(true);
    expect(shouldShowManagedGroupMemberships(false, manager)).toBe(false);
    expect(shouldShowManagedGroupMemberships(true, { isOwner: false, role: "librarian" })).toBe(false);
  });
});
