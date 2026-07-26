import type { BreadcrumbItem } from "../../app/navigation/breadcrumbs";

export const groupsListBreadcrumbFallback = [] as const;

export function groupDetailBreadcrumbFallback(name = "Group"): BreadcrumbItem[] {
  return [
    { label: "Groups", to: "/groups", resetTrail: true },
    { label: name },
  ];
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
