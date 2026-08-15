import {
  addGroupMember,
  getManagedUser,
  listAssignableGroupsForUser,
  removeGroupMember,
  resetManagedUserPassword,
  updateManagedUser,
  updateGroupMember,
  type AssignableGroup,
  type ManagedPasswordResetResult,
  type ManagedUser,
  type ManagedUserGroup,
  type UpdateManagedUserInput,
} from "@second-pass/spl-api";
import { useEffect, useMemo, useState } from "react";
import { Link, useOutletContext, useParams } from "react-router";

import type { AppOutletContext } from "../../../app/layout/AppOrchestrator";
import { usePageBreadcrumbs } from "../../../app/navigation/usePageBreadcrumbs";
import { ErrorPanel } from "../../../components/UiPrimitives";
import { idleMutationState, normalizeMutationError, type MutationState } from "../../../shared/feedback/mutationState";
import { ProductPageShell } from "../../../shared/layout/ProductPageShell";
import { UserInlineIdentity } from "../../../shared/users/UserInlineIdentity";
import { UserDetailsPageRegion } from "./UserDetailsPageRegion";
import { UserGroupMembershipsPageRegion } from "./UserGroupMembershipsPageRegion";
import { UserPasswordPageRegion } from "./UserPasswordPageRegion";
import { editableUserRoles } from "../userCreateRoles";
import { usersEditBreadcrumbFallbackFor } from "../usersBreadcrumbs";
import { confirmGroupMembershipRemoval, confirmManagedPasswordReset } from "./userEditConfirmations";
import "../Users.css";

interface UserEditLoadState {
  loading: boolean;
  user?: ManagedUser;
  assignableGroups: AssignableGroup[];
  error?: Error;
}

export function UserEditOrchestrator() {
  const { profileId = "" } = useParams();
  const { currentUser, serverInfo } = useOutletContext<AppOutletContext>();
  const [retry, setRetry] = useState(0);
  const [load, setLoad] = useState<UserEditLoadState>({ loading: true, assignableGroups: [] });
  const [detailsState, setDetailsState] = useState<MutationState>(idleMutationState);
  const [requirementState, setRequirementState] = useState<MutationState>(idleMutationState);
  const [resetState, setResetState] = useState<MutationState>(idleMutationState);
  const [resetResult, setResetResult] = useState<ManagedPasswordResetResult>();
  const [membershipState, setMembershipState] = useState<MutationState>(idleMutationState);
  const breadcrumbs = useMemo(() => usersEditBreadcrumbFallbackFor(load.user?.username), [load.user?.username]);
  usePageBreadcrumbs(breadcrumbs);

  useEffect(() => {
    let active = true;
    setLoad((value) => ({ ...value, loading: true, error: undefined }));
    const groups = serverInfo.advancedLibraryGroupsEnabled ? listAssignableGroupsForUser(profileId) : Promise.resolve([]);
    Promise.all([getManagedUser(profileId), groups])
      .then(([user, assignableGroups]) => { if (active) setLoad({ loading: false, user, assignableGroups }); })
      .catch((error: unknown) => { if (active) setLoad({ loading: false, assignableGroups: [], error: normalizeMutationError(error) }); });
    return () => { active = false; };
  }, [profileId, retry, serverInfo.advancedLibraryGroupsEnabled]);

  const user = load.user;
  const isSelf = user?.id === currentUser.profileId;
  const managerCanManageTarget = currentUser.role === "manager" && !user?.isOwner && user?.role !== "manager" && !isSelf;
  const canManageTarget = Boolean(user && (currentUser.isOwner || managerCanManageTarget));
  const canEditDetails = Boolean(user && (currentUser.isOwner || managerCanManageTarget));
  const canChangeActive = canManageTarget && !isSelf;
  const canManagePassword = canManageTarget && !isSelf;

  async function reloadUserAndGroups(): Promise<ManagedUser> {
    const [updated, assignableGroups] = await Promise.all([
      getManagedUser(profileId),
      serverInfo.advancedLibraryGroupsEnabled ? listAssignableGroupsForUser(profileId) : Promise.resolve([]),
    ]);
    setLoad({ loading: false, user: updated, assignableGroups });
    return updated;
  }

  async function saveDetails(input: UpdateManagedUserInput) {
    setDetailsState({ pending: true });
    try {
      const updated = await updateManagedUser(profileId, input);
      setLoad((value) => ({ ...value, user: updated }));
      setDetailsState({ pending: false, message: "User saved." });
    } catch (error: unknown) { setDetailsState({ pending: false, error: normalizeMutationError(error) }); }
  }

  async function changePasswordRequirement(value: boolean) {
    setRequirementState({ pending: true });
    try {
      const updated = await updateManagedUser(profileId, { mustChangePassword: value });
      setLoad((current) => ({ ...current, user: updated }));
      setRequirementState({ pending: false, message: "Password requirement saved." });
    } catch (error: unknown) { setRequirementState({ pending: false, error: normalizeMutationError(error) }); }
  }

  async function resetPassword() {
    if (!user || !confirmManagedPasswordReset()) return;
    setResetState({ pending: true });
    setResetResult(undefined);
    try {
      const result = await resetManagedUserPassword(profileId);
      setResetResult(result);
      await reloadUserAndGroups();
      setResetState({ pending: false, message: "Password reset." });
    } catch (error: unknown) { setResetState({ pending: false, error: normalizeMutationError(error) }); }
  }

  async function runMembershipAction(action: () => Promise<unknown>, success: string) {
    setMembershipState({ pending: true });
    try {
      await action();
      await reloadUserAndGroups();
      setMembershipState({ pending: false, message: success });
    } catch (error: unknown) { setMembershipState({ pending: false, error: normalizeMutationError(error) }); }
  }

  function removeMembership(membership: ManagedUserGroup) {
    if (!confirmGroupMembershipRemoval(membership.name)) return;
    void runMembershipAction(() => removeGroupMember(membership.id, profileId), "Membership removed.");
  }

  if (load.loading && !user) return <div className="users-results-state" aria-busy="true">Loading user…</div>;
  if (load.error || !user) return <div className="users-results-state"><ErrorPanel>{load.error?.message ?? "User not found."}</ErrorPanel><button type="button" onClick={() => setRetry((value) => value + 1)}>Retry</button><Link to="/users">Back to Users</Link></div>;

  const displayName = [user.firstName, user.lastName].filter(Boolean).join(" ") || undefined;
  return <ProductPageShell className="users-page user-edit-page" title={<span className="page-header__title-content"><span>Editing User:</span><UserInlineIdentity username={user.username} displayName={displayName} /></span>} actions={<Link className="button button--secondary" to="/users">Back to Users</Link>}>
    <UserDetailsPageRegion
      user={user}
      roles={editableUserRoles(currentUser, user)}
      canEdit={canEditDetails}
      canChangeActive={canChangeActive}
      state={detailsState}
      onSave={saveDetails}
      onClearStatus={() => setDetailsState(idleMutationState)}
    />
    <UserPasswordPageRegion
      mustChangePassword={user.mustChangePassword}
      canManage={canManagePassword}
      requirementState={requirementState}
      resetState={resetState}
      resetResult={resetResult}
      onRequirementChange={(value) => void changePasswordRequirement(value)}
      onReset={() => void resetPassword()}
    />
    {shouldShowManagedGroupMemberships(serverInfo.advancedLibraryGroupsEnabled, currentUser) ? <UserGroupMembershipsPageRegion
      memberships={user.groups}
      assignableGroups={load.assignableGroups}
      state={membershipState}
      onAdd={(groupId, isCurator) => void runMembershipAction(() => addGroupMember(groupId, { userId: profileId, isCurator }), "Membership added.")}
      onRemove={removeMembership}
      onCuratorChange={(membership, isCurator) => void runMembershipAction(() => updateGroupMember(membership.id, profileId, { isCurator }), "Curator access saved.")}
    /> : null}
  </ProductPageShell>;
}

export function shouldShowManagedGroupMemberships(
  advancedGroupsEnabled: boolean,
  operator: { isOwner: boolean; role: string },
): boolean {
  return advancedGroupsEnabled && (operator.isOwner || operator.role === "manager");
}
