import {
  isAtLeastLibrarian,
  isAtLeastManager,
  type CurrentUser,
  type LibraryGroup,
} from "@second-pass/spl-api";

export type GroupMetadataAuthority = "none" | "description" | "full";

export function canCreateGroupMetadata(user: CurrentUser, advancedGroupsEnabled: boolean): boolean {
  return advancedGroupsEnabled && isAtLeastManager(user);
}

export function groupMetadataAuthority(
  user: CurrentUser,
  group: Pick<LibraryGroup, "id" | "isPublicGroup">,
  advancedGroupsEnabled: boolean,
): GroupMetadataAuthority {
  if (!advancedGroupsEnabled || group.isPublicGroup) return "none";
  if (isAtLeastManager(user)) return "full";
  if (isAtLeastLibrarian(user)) return "description";
  return user.groups.some(({ id, isCurator }) => id === group.id && isCurator)
    ? "description"
    : "none";
}

export function canMutateGroupBooks(
  user: CurrentUser,
  group: Pick<LibraryGroup, "id" | "isPublicGroup">,
  advancedGroupsEnabled: boolean,
): boolean {
  if (!advancedGroupsEnabled) return false;
  if (isAtLeastLibrarian(user)) return true;
  return !group.isPublicGroup && user.groups.some(
    ({ id, isCurator }) => id === group.id && isCurator,
  );
}

export function canMutateGroupMembers(user: CurrentUser, advancedGroupsEnabled: boolean): boolean {
  return advancedGroupsEnabled && isAtLeastManager(user);
}

export function canDeleteGroup(
  user: CurrentUser,
  group: Pick<LibraryGroup, "isPublicGroup">,
  advancedGroupsEnabled: boolean,
): boolean {
  return advancedGroupsEnabled && !group.isPublicGroup && isAtLeastManager(user);
}

export function canManageGroup(
  user: CurrentUser,
  group: Pick<LibraryGroup, "id" | "isPublicGroup">,
  advancedGroupsEnabled: boolean,
): boolean {
  return groupMetadataAuthority(user, group, advancedGroupsEnabled) !== "none"
    || canMutateGroupBooks(user, group, advancedGroupsEnabled)
    || canMutateGroupMembers(user, advancedGroupsEnabled)
    || canDeleteGroup(user, group, advancedGroupsEnabled);
}
