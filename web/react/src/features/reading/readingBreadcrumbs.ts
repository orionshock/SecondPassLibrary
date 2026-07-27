import type { BreadcrumbItem } from "../../app/navigation/breadcrumbs";

export const readingListBreadcrumbFallback = [] as const;

export const readingImportBreadcrumbFallback: readonly BreadcrumbItem[] = [
  { label: "My Marginalia", to: "/reading", resetTrail: true },
  { label: "Import", icon: "import" },
];
