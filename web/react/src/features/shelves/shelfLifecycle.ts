import {
  isAtLeastLibrarian,
  type CurrentUser,
  type LibraryGroup,
  type ShelfSummary,
} from "@second-pass/spl-api";

import {
  breadcrumbNavigationState,
  readIncomingBreadcrumbTrail,
  type BreadcrumbItem,
} from "../../app/navigation/breadcrumbs";
import { confirmDangerousAction } from "../../shared/confirmations/confirmDangerousAction";
import { shelfDetailBreadcrumbFallback } from "./shelvesBreadcrumbs";

export type ShelfLifecycleMode = "new" | "edit";

export function shelfNewPath(): string {
  return "/shelves/new";
}

export function shelfEditPath(shelfId: string): string {
  return `/shelves/${encodeURIComponent(shelfId)}/edit`;
}

export function shelfDetailPathForId(shelfId: string): string {
  return `/shelves/${encodeURIComponent(shelfId)}`;
}

export function shelfNewBreadcrumbs(): BreadcrumbItem[] {
  return [
    { label: "Shelves", to: "/shelves", resetTrail: true },
    { label: "New Shelf" },
  ];
}

export function shelfEditBreadcrumbs(shelfId: string, name = "Shelf"): BreadcrumbItem[] {
  return [
    { label: "Shelves", to: "/shelves", resetTrail: true },
    { label: name, to: shelfDetailPathForId(shelfId) },
    { label: "Edit" },
  ];
}

export function shelfEditNavigationState(
  currentState: unknown,
  shelf: Pick<ShelfSummary, "id" | "name">,
): object {
  const incoming = readIncomingBreadcrumbTrail(currentState);
  const trail = incoming?.length
    ? [
      ...incoming.slice(0, -1),
      { label: shelf.name, to: shelfDetailPathForId(shelf.id) },
      { label: "Edit" },
    ]
    : shelfEditBreadcrumbs(shelf.id, shelf.name);
  return breadcrumbNavigationState(trail);
}

export function shelfDetailNavigationStateFromEdit(
  currentState: unknown,
  shelf: Pick<ShelfSummary, "id" | "name">,
): object {
  const incoming = readIncomingBreadcrumbTrail(currentState);
  if (incoming && incoming.at(-1)?.label === "Edit") {
    const detailTrail = incoming.slice(0, -1);
    const last = detailTrail.length - 1;
    detailTrail[last] = { label: shelf.name };
    return breadcrumbNavigationState(detailTrail);
  }
  return breadcrumbNavigationState(shelfDetailBreadcrumbFallback(shelf.name));
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

export function localManageableShelfGroups(user: CurrentUser): LibraryGroup[] {
  if (isAtLeastLibrarian(user)) {
    if (user.advancedLibraryGroupsEnabled) return [];
    return user.groups.filter(({ isPublicGroup }) => isPublicGroup).map(currentGroupAsLibraryGroup);
  }
  if (!user.advancedLibraryGroupsEnabled) return [];
  return user.groups
    .filter(({ isCurator, isPublicGroup }) => isCurator && !isPublicGroup)
    .map(currentGroupAsLibraryGroup);
}

export function shouldLoadAllShelfGroups(user: CurrentUser): boolean {
  return isAtLeastLibrarian(user) && user.advancedLibraryGroupsEnabled;
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
