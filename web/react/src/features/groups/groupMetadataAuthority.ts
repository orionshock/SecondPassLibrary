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

export function canManageGroup(
  user: CurrentUser,
  group: Pick<LibraryGroup, "id" | "isPublicGroup">,
): boolean {
  return groupMetadataAuthority(user, group) !== "none"
    || canMutateGroupBooks(user, group)
    || canMutateGroupMembers(user)
    || canDeleteGroup(user, group);
}

export function initialGroupEditTab(
  user: CurrentUser,
  group: Pick<LibraryGroup, "id" | "isPublicGroup">,
): "details" | "books" | "members" {
  if (!group.isPublicGroup) return "details";
  if (canMutateGroupBooks(user, group)) return "books";
  if (canMutateGroupMembers(user)) return "members";
  return "details";
}
