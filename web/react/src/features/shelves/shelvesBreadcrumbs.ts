import type { BreadcrumbItem } from "../../app/navigation/breadcrumbs";

export const shelvesListBreadcrumbFallback = [] as const;

export function shelfDetailBreadcrumbFallback(name = "Shelf"): BreadcrumbItem[] {
  return [
    { label: "Shelves", to: "/shelves", resetTrail: true },
    { label: name },
  ];
}

export function shelfBookBreadcrumbs(
  shelfId: string,
  shelfName: string,
  bookTitle: string,
  shelfPath = `/shelves/${encodeURIComponent(shelfId)}`,
): BreadcrumbItem[] {
  return [
    { label: "Shelves", to: "/shelves", resetTrail: true },
    { label: shelfName, to: shelfPath },
    { label: bookTitle },
  ];
}
