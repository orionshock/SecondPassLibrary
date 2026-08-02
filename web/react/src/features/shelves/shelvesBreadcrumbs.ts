import type { ShelfScope } from "@second-pass/spl-api";

import type { BreadcrumbItem } from "../../app/navigation/breadcrumbs";
import { shelfScopeBreadcrumb } from "./shelfScopes";

export const shelvesListBreadcrumbFallback = [] as const;

export function shelfDetailBreadcrumbFallback(scope: ShelfScope, name = "Shelf"): BreadcrumbItem[] {
  return [
    { label: "Shelves", to: "/shelves", resetTrail: true, icon: "shelf" },
    shelfScopeBreadcrumb(scope),
    { label: name, icon: "shelf" },
  ];
}

export function shelfBookBreadcrumbs(
  scope: ShelfScope,
  shelfId: string,
  shelfName: string,
  bookTitle: string,
  shelfPath = `/shelves/${encodeURIComponent(shelfId)}`,
): BreadcrumbItem[] {
  return [
    { label: "Shelves", to: "/shelves", resetTrail: true, icon: "shelf" },
    shelfScopeBreadcrumb(scope),
    { label: shelfName, to: shelfPath, icon: "shelf" },
    { label: bookTitle, icon: "book" },
  ];
}
