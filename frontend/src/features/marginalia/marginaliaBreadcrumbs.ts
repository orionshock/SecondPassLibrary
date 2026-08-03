import type { BreadcrumbItem } from "../../app/navigation/breadcrumbs";
import { marginaliaSessionDisplayName } from "../../shared/marginaliaSessionDisplayName";

export const marginaliaListBreadcrumbFallback = [] as const;

export const marginaliaImportBreadcrumbFallback: readonly BreadcrumbItem[] = [
  { label: "My Marginalia", to: "/marginalia", resetTrail: true },
  { label: "Import", icon: "import" },
];

export const marginaliaExportBreadcrumbFallback: readonly BreadcrumbItem[] = [
  { label: "My Marginalia", to: "/marginalia", resetTrail: true },
  { label: "Export" },
];

export function marginaliaSessionBreadcrumbFallback(session?: { id: string; name: string }): readonly BreadcrumbItem[] {
  return [
    { label: "My Marginalia", to: "/marginalia", resetTrail: true },
    { label: session ? marginaliaSessionDisplayName(session) : "Session" },
  ];
}
