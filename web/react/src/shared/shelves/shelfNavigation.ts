import { breadcrumbNavigationState } from "../../app/navigation/breadcrumbs";

interface ShelfAuthorityUser {
  isOwner: boolean;
  isManager: boolean;
  isLibrarian: boolean;
  groups: readonly { id: string; isCurator: boolean }[];
}

interface ShelfOwnerGroup {
  id: string;
  isPublicGroup: boolean;
}

interface ShelfOwnerGroupPresentation extends ShelfOwnerGroup {
  name: string;
}

export interface ShelfCreateGroupContext {
  groupId: string;
  groupName: string;
  isPublicGroup: boolean;
  returnTo: string;
}

const shelfCreateGroupContextKey = "shelfCreateGroupContext";

export function shelfNewPath(): string {
  return "/shelves/new";
}

export function shelfEditPath(shelfId: string): string {
  return `/shelves/${encodeURIComponent(shelfId)}/edit`;
}

export function shelfDetailPathForId(shelfId: string): string {
  return `/shelves/${encodeURIComponent(shelfId)}`;
}

export function canCreateShelfForGroup(
  user: ShelfAuthorityUser,
  group: ShelfOwnerGroup,
): boolean {
  if (user.isOwner || user.isManager || user.isLibrarian) return true;
  if (group.isPublicGroup) return false;
  return user.groups.some(({ id, isCurator }) => id === group.id && isCurator);
}

export function shelfCreateNavigationStateForGroup(
  group: ShelfOwnerGroupPresentation,
  returnTo: string,
): object {
  const context: ShelfCreateGroupContext = {
    groupId: group.id,
    groupName: group.name,
    isPublicGroup: group.isPublicGroup,
    returnTo,
  };
  return {
    ...breadcrumbNavigationState([
      { label: "Groups", to: "/groups", resetTrail: true, icon: "group" },
      {
        label: group.name,
        to: returnTo,
        icon: group.isPublicGroup ? "public-group" : "group",
      },
      { label: "New Shelf" },
    ]),
    [shelfCreateGroupContextKey]: context,
  };
}

export function readShelfCreateGroupContext(state: unknown): ShelfCreateGroupContext | undefined {
  if (!isRecord(state)) return undefined;
  const value = state[shelfCreateGroupContextKey];
  if (!isRecord(value)) return undefined;
  if (typeof value.groupId !== "string" || !value.groupId || value.groupId.length > 128) return undefined;
  if (typeof value.groupName !== "string" || !value.groupName.trim() || value.groupName.length > 255) return undefined;
  if (typeof value.isPublicGroup !== "boolean") return undefined;
  if (typeof value.returnTo !== "string" || !isGroupReturnPath(value.returnTo, value.groupId)) return undefined;
  return {
    groupId: value.groupId,
    groupName: value.groupName.trim(),
    isPublicGroup: value.isPublicGroup,
    returnTo: value.returnTo,
  };
}

export function authorizedShelfCreateGroupContext(
  user: ShelfAuthorityUser,
  state: unknown,
): ShelfCreateGroupContext | undefined {
  const context = readShelfCreateGroupContext(state);
  if (!context) return undefined;
  return canCreateShelfForGroup(user, {
    id: context.groupId,
    isPublicGroup: context.isPublicGroup,
  })
    ? context
    : undefined;
}

export function shelfCreateGroupReturnNavigationState(context: ShelfCreateGroupContext): object {
  return breadcrumbNavigationState([
    { label: "Groups", to: "/groups", resetTrail: true, icon: "group" },
    { label: context.groupName, icon: context.isPublicGroup ? "public-group" : "group" },
  ]);
}

function isGroupReturnPath(value: string, groupId: string): boolean {
  const groupPath = `/groups/${encodeURIComponent(groupId)}`;
  return value === groupPath || value.startsWith(`${groupPath}?`);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
