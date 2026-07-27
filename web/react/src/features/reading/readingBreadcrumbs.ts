import type { BreadcrumbItem } from "../../app/navigation/breadcrumbs";

export const readingListBreadcrumbFallback = [] as const;

export const readingImportBreadcrumbFallback: readonly BreadcrumbItem[] = [
  { label: "My Marginalia", to: "/reading", resetTrail: true },
  { label: "Import", icon: "import" },
];

export function readingSessionBreadcrumbFallback(sessionName?: string): readonly BreadcrumbItem[] {
  return [
    { label: "My Marginalia", to: "/reading", resetTrail: true },
    { label: sessionName?.trim() || "Session" },
  ];
}
