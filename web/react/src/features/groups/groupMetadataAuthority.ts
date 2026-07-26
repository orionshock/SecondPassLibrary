import {
  isAtLeastLibrarian,
  isAtLeastManager,
  type CurrentUser,
  type LibraryGroup,
} from "@second-pass/spl-api";

export type GroupMetadataAuthority = "none" | "description" | "full";

export function canCreateGroupMetadata(user: CurrentUser): boolean {
  return user.advancedLibraryGroupsEnabled && isAtLeastManager(user);
}

export function groupMetadataAuthority(
  user: CurrentUser,
  group: Pick<LibraryGroup, "id" | "isPublicGroup">,
): GroupMetadataAuthority {
  if (!user.advancedLibraryGroupsEnabled || group.isPublicGroup) return "none";
  if (isAtLeastManager(user)) return "full";
  if (isAtLeastLibrarian(user)) return "description";
  return user.groups.some(({ id, isCurator }) => id === group.id && isCurator)
    ? "description"
    : "none";
}

export function canMutateGroupBooks(
  user: CurrentUser,
  group: Pick<LibraryGroup, "id" | "isPublicGroup">,
): boolean {
  if (!user.advancedLibraryGroupsEnabled) return false;
  if (isAtLeastLibrarian(user)) return true;
  return !group.isPublicGroup && user.groups.some(
    ({ id, isCurator }) => id === group.id && isCurator,
  );
}

export function canMutateGroupMembers(user: CurrentUser): boolean {
  return user.advancedLibraryGroupsEnabled && isAtLeastManager(user);
}

export function canDeleteGroup(
  user: CurrentUser,
  group: Pick<LibraryGroup, "isPublicGroup">,
): boolean {
  return user.advancedLibraryGroupsEnabled && !group.isPublicGroup && isAtLeastManager(user);
}
