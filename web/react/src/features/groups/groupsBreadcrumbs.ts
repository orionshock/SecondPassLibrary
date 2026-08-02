import type { LibraryGroup } from "@second-pass/spl-api";

import {
  breadcrumbNavigationState,
  readIncomingBreadcrumbTrail,
  type BreadcrumbItem,
} from "../../app/navigation/breadcrumbs";

export const groupsListBreadcrumbFallback = [] as const;

export function groupDetailBreadcrumbFallback(name = "Group", isPublicGroup = false): BreadcrumbItem[] {
  return [
    { label: "Groups", to: "/groups", resetTrail: true, icon: "group" },
    { label: name, icon: groupBreadcrumbIcon(isPublicGroup) },
  ];
}

export function groupNewBreadcrumbs(): BreadcrumbItem[] {
  return [
    { label: "Groups", to: "/groups", resetTrail: true, icon: "group" },
    { label: "New Group" },
  ];
}

export function groupEditBreadcrumbFallback(groupId: string, name = "Group", isPublicGroup = false): BreadcrumbItem[] {
  return [
    { label: "Groups", to: "/groups", resetTrail: true, icon: "group" },
    { label: name, to: groupDetailPath(groupId), icon: groupBreadcrumbIcon(isPublicGroup) },
    { label: "Edit" },
  ];
}

export function groupDetailPath(groupId: string): string {
  return `/groups/${encodeURIComponent(groupId)}`;
}

export function groupEditPath(groupId: string): string {
  return `${groupDetailPath(groupId)}/edit`;
}

export function groupEditNavigationState(
  currentState: unknown,
  group: Pick<LibraryGroup, "id" | "name" | "isPublicGroup">,
  successMessage?: string,
): object {
  const incoming = readIncomingBreadcrumbTrail(currentState);
  const parent = incoming?.at(-1)?.label === "Edit"
    ? incoming.slice(0, -2)
    : incoming?.slice(0, -1);
  const trail = [
    ...(parent?.length ? parent : [{ label: "Groups", to: "/groups", resetTrail: true, icon: "group" as const }]),
    { label: group.name, to: groupDetailPath(group.id), icon: groupBreadcrumbIcon(group.isPublicGroup) },
    { label: "Edit" },
  ];
  return {
    ...breadcrumbNavigationState(trail),
    ...(successMessage ? { groupLifecycleSuccessMessage: successMessage } : {}),
  };
}

export function groupDetailNavigationStateFromEdit(
  currentState: unknown,
  group: Pick<LibraryGroup, "id" | "name" | "isPublicGroup">,
): object {
  const incoming = readIncomingBreadcrumbTrail(currentState);
  if (incoming?.at(-1)?.label === "Edit") {
    const trail = incoming.slice(0, -1);
    trail[trail.length - 1] = { label: group.name, icon: groupBreadcrumbIcon(group.isPublicGroup) };
    return breadcrumbNavigationState(trail);
  }
  return breadcrumbNavigationState(groupDetailBreadcrumbFallback(group.name, group.isPublicGroup));
}

export function readGroupLifecycleSuccessMessage(state: unknown): string | undefined {
  if (typeof state !== "object" || state === null) return undefined;
  const message = (state as Record<string, unknown>).groupLifecycleSuccessMessage;
  return typeof message === "string" ? message : undefined;
}

export function groupBookBreadcrumbs(
  groupId: string,
  groupName: string,
  bookTitle: string,
  groupPath = `/groups/${encodeURIComponent(groupId)}`,
  isPublicGroup = false,
): BreadcrumbItem[] {
  return [
    { label: "Groups", to: "/groups", resetTrail: true, icon: "group" },
    { label: groupName, to: groupPath, icon: groupBreadcrumbIcon(isPublicGroup) },
    { label: bookTitle, icon: "book" },
  ];
}

export function groupShelfBreadcrumbs(
  groupId: string,
  groupName: string,
  shelfName: string,
  shelvesPath: string,
  isPublicGroup = false,
): BreadcrumbItem[] {
  return [
    { label: "Groups", to: "/groups", resetTrail: true, icon: "group" },
    { label: groupName, to: groupDetailPath(groupId), icon: groupBreadcrumbIcon(isPublicGroup) },
    { label: "Shelves", to: shelvesPath, icon: "shelf" },
    { label: shelfName, icon: "shelf" },
  ];
}

export function groupShelfBookBreadcrumbs(
  groupId: string,
  groupName: string,
  shelfId: string,
  shelfName: string,
  bookTitle: string,
  shelvesPath: string,
  isPublicGroup = false,
): BreadcrumbItem[] {
  const trail = groupShelfBreadcrumbs(groupId, groupName, shelfName, shelvesPath, isPublicGroup);
  trail[trail.length - 1] = {
    label: shelfName,
    to: `/shelves/${encodeURIComponent(shelfId)}`,
    icon: "shelf",
  };
  return [...trail, { label: bookTitle, icon: "book" }];
}

export function groupShelfEditBreadcrumbs(
  groupId: string,
  groupName: string,
  shelfId: string,
  shelfName: string,
  shelvesPath: string,
  isPublicGroup = false,
): BreadcrumbItem[] {
  const trail = groupShelfBreadcrumbs(groupId, groupName, shelfName, shelvesPath, isPublicGroup);
  trail[trail.length - 1] = {
    label: shelfName,
    to: `/shelves/${encodeURIComponent(shelfId)}`,
    icon: "shelf",
  };
  return [...trail, { label: "Edit" }];
}

function groupBreadcrumbIcon(isPublicGroup: boolean): "group" | "public-group" {
  return isPublicGroup ? "public-group" : "group";
}
