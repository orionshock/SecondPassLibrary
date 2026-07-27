import type { BreadcrumbItem } from "../../app/navigation/breadcrumbs";

export const marginaliaListBreadcrumbFallback = [] as const;

export const marginaliaImportBreadcrumbFallback: readonly BreadcrumbItem[] = [
  { label: "My Marginalia", to: "/marginalia", resetTrail: true },
  { label: "Import", icon: "import" },
];

export const marginaliaExportBreadcrumbFallback: readonly BreadcrumbItem[] = [
  { label: "My Marginalia", to: "/marginalia", resetTrail: true },
  { label: "Export" },
];

export function marginaliaSessionBreadcrumbFallback(sessionName?: string): readonly BreadcrumbItem[] {
  return [
    { label: "My Marginalia", to: "/marginalia", resetTrail: true },
    { label: sessionName?.trim() || "Session" },
  ];
}
