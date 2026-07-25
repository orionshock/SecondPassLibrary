import type { BreadcrumbItem } from "../../app/navigation/breadcrumbs";

export const usersListBreadcrumbFallback: readonly BreadcrumbItem[] = [];
export const usersCreateBreadcrumbFallback: readonly BreadcrumbItem[] = [
  { label: "Users", to: "/users", resetTrail: true },
  { label: "New" },
];
export function usersEditBreadcrumbTrail(username: string): BreadcrumbItem[] {
  return [...usersEditBreadcrumbFallbackFor(username)];
}

export function usersEditBreadcrumbFallbackFor(username?: string): readonly BreadcrumbItem[] {
  return [
    { label: "Users", to: "/users", resetTrail: true },
    { label: username ? `@${username}` : "User" },
    { label: "Edit" },
  ];
}
