import {
  isAtLeastLibrarian,
  type CurrentUser,
  type LibraryGroup,
  type ShelfScope,
  type ShelfSummary,
} from "@second-pass/spl-api";

import {
  breadcrumbNavigationState,
  readIncomingBreadcrumbTrail,
  type BreadcrumbItem,
} from "../../app/navigation/breadcrumbs";
import { confirmDangerousAction } from "../../shared/confirmations/confirmDangerousAction";
import { shelfDetailPathForId } from "../../shared/shelves/shelfNavigation";
import { shelfDetailBreadcrumbFallback } from "./shelvesBreadcrumbs";
import { shelfScopeBreadcrumb, shelfScopeFromSummary } from "./shelfScopes";

export type ShelfLifecycleMode = "new" | "edit";

export function shelfNewBreadcrumbs(scope: ShelfScope = "personal"): BreadcrumbItem[] {
  return [
    { label: "Shelves", to: "/shelves", resetTrail: true, icon: "shelf" },
    shelfScopeBreadcrumb(scope),
    { label: "New Shelf" },
  ];
}

export function shelfEditBreadcrumbs(
  shelfId: string,
  name = "Shelf",
  scope: ShelfScope = "personal",
): BreadcrumbItem[] {
  return [
    { label: "Shelves", to: "/shelves", resetTrail: true, icon: "shelf" },
    shelfScopeBreadcrumb(scope),
    { label: name, to: shelfDetailPathForId(shelfId), icon: "shelf" },
    { label: "Edit" },
  ];
}

export function shelfEditNavigationState(
  currentState: unknown,
  shelf: Pick<ShelfSummary, "id" | "name" | "ownerType" | "canEdit">,
): object {
  const incoming = readIncomingBreadcrumbTrail(currentState);
  const trail: BreadcrumbItem[] = incoming?.length
    ? [
      ...incoming.slice(0, -1),
      { label: shelf.name, to: shelfDetailPathForId(shelf.id), icon: "shelf" },
      { label: "Edit" },
    ]
    : shelfEditBreadcrumbs(shelf.id, shelf.name, shelfScopeFromSummary(shelf));
  return breadcrumbNavigationState(trail);
}

export function shelfDetailNavigationStateFromEdit(
  currentState: unknown,
  shelf: Pick<ShelfSummary, "id" | "name" | "ownerType" | "canEdit">,
): object {
  const incoming = readIncomingBreadcrumbTrail(currentState);
  if (incoming && incoming.at(-1)?.label === "Edit") {
    const detailTrail = incoming.slice(0, -1);
    const last = detailTrail.length - 1;
    detailTrail[last] = { label: shelf.name, icon: "shelf" };
    return breadcrumbNavigationState(detailTrail);
  }
  return breadcrumbNavigationState(shelfDetailBreadcrumbFallback(shelfScopeFromSummary(shelf), shelf.name));
}

export function shelfLifecycleNavigationState(
  trail: readonly BreadcrumbItem[],
  successMessage?: string,
): object {
  return {
    ...breadcrumbNavigationState(trail),
    ...(successMessage ? { shelfLifecycleSuccessMessage: successMessage } : {}),
  };
}

export function readShelfLifecycleSuccessMessage(state: unknown): string | undefined {
  if (!isRecord(state) || typeof state.shelfLifecycleSuccessMessage !== "string") return undefined;
  return state.shelfLifecycleSuccessMessage;
}

export function localManageableShelfGroups(user: CurrentUser, advancedGroupsEnabled: boolean): LibraryGroup[] {
  if (isAtLeastLibrarian(user)) {
    if (advancedGroupsEnabled) return [];
    return user.groups.filter(({ isPublicGroup }) => isPublicGroup).map(currentGroupAsLibraryGroup);
  }
  if (!advancedGroupsEnabled) return [];
  return user.groups
    .filter(({ isCurator, isPublicGroup }) => isCurator && !isPublicGroup)
    .map(currentGroupAsLibraryGroup);
}

export function shouldLoadAllShelfGroups(user: CurrentUser, advancedGroupsEnabled: boolean): boolean {
  return isAtLeastLibrarian(user) && advancedGroupsEnabled;
}

export function confirmShelfDelete(
  confirmAction: (message: string) => boolean = window.confirm,
): boolean {
  return confirmDangerousAction(
    "Delete this shelf? This will remove the shelf and its shelf items. Books and files will not be deleted.",
    confirmAction,
  );
}

export function confirmUnavailableShelfItemRemoval(
  confirmAction: (message: string) => boolean = window.confirm,
): boolean {
  return confirmDangerousAction(
    "Remove this unavailable item from the shelf? Its retained shelf position will be discarded.",
    confirmAction,
  );
}

function currentGroupAsLibraryGroup(group: CurrentUser["groups"][number]): LibraryGroup {
  return {
    id: group.id,
    name: group.name,
    description: "",
    isPublicGroup: group.isPublicGroup,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
