import { appendBreadcrumbTrail, type BreadcrumbItem } from "../../app/navigation/breadcrumbs";

export const usersListBreadcrumbFallback: readonly BreadcrumbItem[] = [];
export const usersCreateBreadcrumbFallback: readonly BreadcrumbItem[] = [
  { label: "Users", to: "/users" },
  { label: "New" },
];
export const usersEditBreadcrumbFallback: readonly BreadcrumbItem[] = [
  { label: "Users", to: "/users" },
  { label: "Edit user" },
];

export function usersEditBreadcrumbTrail(name: string): BreadcrumbItem[] {
  return appendBreadcrumbTrail(
    [{ label: "Users", to: "/users" }, { label: `User: ${name}` }],
    { label: "Edit" },
  );
}
