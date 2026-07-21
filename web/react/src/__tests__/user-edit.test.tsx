import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ApiError, type CurrentUser, type ManagedPasswordResetResult, type ManagedUser } from "@second-pass/spl-api";
import { UserDetailsPageRegion } from "../features/users/regions/UserDetailsPageRegion";
import { UserGroupMembershipsPageRegion } from "../features/users/regions/UserGroupMembershipsPageRegion";
import { UserPasswordPageRegion } from "../features/users/regions/UserPasswordPageRegion";
import { shouldShowManagedGroupMemberships } from "../features/users/UserEditOrchestrator";
import { userEditDraftFromUser, userEditDraftReducer } from "../features/users/userEditForm";
import { editableUserRoles } from "../features/users/userCreateRoles";
import { usersEditBreadcrumbFallbackFor, usersEditBreadcrumbTrail } from "../features/users/usersBreadcrumbs";
import { confirmGroupMembershipRemoval, confirmManagedPasswordReset } from "../features/users/userEditConfirmations";

const target: ManagedUser = {
  id: "target", username: "reader", firstName: "Read", lastName: "Er", email: "reader@example.test", role: "reader",
  isOwner: false, isActive: true, dateJoined: "2026-01-01T00:00:00Z", lastLogin: null, mustChangePassword: false,
  groups: [{ id: "public", name: "Common Room", isPublicGroup: true, isCurator: false }, { id: "custom", name: "Book Club", isPublicGroup: false, isCurator: true }],
};
const owner: CurrentUser = { username: "owner", email: "", firstName: "", lastName: "", profileId: "owner", role: "manager", mustChangePassword: false, isOwner: true, advancedLibraryGroupsEnabled: true, bannerText: "", groups: [] };
const manager: CurrentUser = { ...owner, username: "manager", profileId: "manager", isOwner: false };

describe("User Edit", () => {
  it("uses canonical identity breadcrumbs and permission-aware capitalized roles", () => {
    expect(usersEditBreadcrumbFallbackFor("reader")).toEqual([{ label: "Users", to: "/users" }, { label: "@reader" }, { label: "Edit" }]);
    expect(usersEditBreadcrumbTrail("reader")).toEqual(usersEditBreadcrumbFallbackFor("reader"));
    expect(editableUserRoles(owner, target)).toEqual(["manager", "librarian", "reader"]);
    expect(editableUserRoles(manager, target)).toEqual(["librarian", "reader"]);
    expect(editableUserRoles(manager, { ...target, role: "manager" })).toEqual([]);
  });

  it("renders bounded details rows with Active labels, action feedback, and local reset behavior", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><UserDetailsPageRegion user={target} roles={editableUserRoles(owner, target)} canEdit canChangeActive state={{ pending: false, message: "Saved." }} onSave={vi.fn()} onClearStatus={vi.fn()} /></MemoryRouter>);
    expect(markup).toContain('class="form-field"');
    expect(markup).toContain('<option value="active" selected="">Active</option>');
    expect(markup).toContain('<option value="inactive">Inactive</option>');
    expect(markup).not.toContain('>true<');
    expect(markup).toContain('>Manager<');
    expect(markup).toContain('>Librarian<');
    expect(markup).toContain("check_circle");
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
    expect(confirmManagedPasswordReset("reader", vi.fn(() => false))).toBe(false);
    const result: ManagedPasswordResetResult = { username: "reader", temporaryPassword: "one-time", message: "show once" };
    const markup = renderToStaticMarkup(<MemoryRouter><UserPasswordPageRegion mustChangePassword canManage requirementState={{ pending: false }} resetState={{ pending: false, message: "Password reset." }} resetResult={result} onRequirementChange={vi.fn()} onReset={vi.fn()} /></MemoryRouter>);
    expect(markup).toContain('readOnly=""');
    expect(markup).toContain("Username: reader");
    expect(markup).toContain("Password: one-time");
    expect(markup.indexOf("one-time")).toBeLessThan(markup.indexOf("It will not be shown again"));
    expect(markup).toContain("Require password change on next login");
  });

  it("keeps add controls separate and makes Public membership non-destructive/non-curatable", () => {
    expect(confirmGroupMembershipRemoval("Book Club", vi.fn(() => false))).toBe(false);
    const markup = renderToStaticMarkup(<MemoryRouter><UserGroupMembershipsPageRegion memberships={target.groups} assignableGroups={[{ id: "new", name: "New Group", isPublicGroup: false }]} state={{ pending: false }} onAdd={vi.fn()} onRemove={vi.fn()} onCuratorChange={vi.fn()} /></MemoryRouter>);
    expect(markup).toContain("Public Group");
    expect(markup).not.toContain('aria-label="Remove Common Room"');
    expect(markup).toContain('aria-label="Remove Book Club"');
    expect(markup).toContain('class="user-membership-add"');
    expect(markup).toContain("Add to group");
  });

  it("shows group management only in advanced mode for a manageable target", () => {
    expect(shouldShowManagedGroupMemberships(true, true)).toBe(true);
    expect(shouldShowManagedGroupMemberships(false, true)).toBe(false);
    expect(shouldShowManagedGroupMemberships(true, false)).toBe(false);
  });
});
