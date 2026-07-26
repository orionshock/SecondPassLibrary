import type { LibraryGroup } from "@second-pass/spl-api";

import {
  breadcrumbNavigationState,
  readIncomingBreadcrumbTrail,
  type BreadcrumbItem,
} from "../../app/navigation/breadcrumbs";

export const groupsListBreadcrumbFallback = [] as const;

export function groupDetailBreadcrumbFallback(name = "Group"): BreadcrumbItem[] {
  return [
    { label: "Groups", to: "/groups", resetTrail: true },
    { label: name },
  ];
}

export function groupNewBreadcrumbs(): BreadcrumbItem[] {
  return [
    { label: "Groups", to: "/groups", resetTrail: true },
    { label: "New Group" },
  ];
}

export function groupEditBreadcrumbFallback(groupId: string, name = "Group"): BreadcrumbItem[] {
  return [
    { label: "Groups", to: "/groups", resetTrail: true },
    { label: name, to: groupDetailPath(groupId) },
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
  group: Pick<LibraryGroup, "id" | "name">,
  successMessage?: string,
): object {
  const incoming = readIncomingBreadcrumbTrail(currentState);
  const parent = incoming?.at(-1)?.label === "Edit"
    ? incoming.slice(0, -2)
    : incoming?.slice(0, -1);
  const trail = [
    ...(parent?.length ? parent : [{ label: "Groups", to: "/groups", resetTrail: true }]),
    { label: group.name, to: groupDetailPath(group.id) },
    { label: "Edit" },
  ];
  return {
    ...breadcrumbNavigationState(trail),
    ...(successMessage ? { groupLifecycleSuccessMessage: successMessage } : {}),
  };
}

export function groupDetailNavigationStateFromEdit(
  currentState: unknown,
  group: Pick<LibraryGroup, "id" | "name">,
): object {
  const incoming = readIncomingBreadcrumbTrail(currentState);
  if (incoming?.at(-1)?.label === "Edit") {
    const trail = incoming.slice(0, -1);
    trail[trail.length - 1] = { label: group.name };
    return breadcrumbNavigationState(trail);
  }
  return breadcrumbNavigationState(groupDetailBreadcrumbFallback(group.name));
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
): BreadcrumbItem[] {
  return [
    { label: "Groups", to: "/groups", resetTrail: true },
    { label: groupName, to: groupPath },
    { label: bookTitle },
  ];
}

export function groupShelfBreadcrumbs(
  groupId: string,
  groupName: string,
  shelfName: string,
  shelvesPath: string,
): BreadcrumbItem[] {
  return [
    { label: "Groups", to: "/groups", resetTrail: true },
    { label: groupName, to: groupDetailPath(groupId) },
    { label: "Shelves", to: shelvesPath },
    { label: shelfName },
  ];
}
