import type { ShelfScope, ShelfSummary } from "@second-pass/spl-api";

import {
  breadcrumbIconSymbols,
  readIncomingBreadcrumbTrail,
  type BreadcrumbIcon,
  type BreadcrumbItem,
} from "../../app/navigation/breadcrumbs";
import { shelvesListPath } from "./shelvesQuery";

export interface ShelfScopePresentation {
  id: ShelfScope;
  label: string;
  icon: BreadcrumbIcon;
  materialIcon: string;
}

const scopeDefinitions: Readonly<Record<ShelfScope, Omit<ShelfScopePresentation, "id" | "materialIcon">>> = {
  personal: { label: "Personal", icon: "shelf" },
  shared: { label: "Shared by Others", icon: "shared-shelf" },
  group: { label: "Group Shelves", icon: "group-shelf" },
};

export const shelfScopePresentations: readonly ShelfScopePresentation[] = (
  ["personal", "shared", "group"] as const
).map((id) => ({
  id,
  ...scopeDefinitions[id],
  materialIcon: breadcrumbIconSymbols[scopeDefinitions[id].icon],
}));

export function shelfScopePresentation(scope: ShelfScope): ShelfScopePresentation {
  return shelfScopePresentations.find(({ id }) => id === scope)!;
}

export function shelfScopePath(scope: ShelfScope): string {
  return shelvesListPath({ scope, q: "", ordering: "name", page: 1, pageSize: 20 });
}

export function shelfScopeBreadcrumb(scope: ShelfScope): BreadcrumbItem {
  const presentation = shelfScopePresentation(scope);
  return {
    label: presentation.label,
    to: shelfScopePath(scope),
    icon: presentation.icon,
  };
}

export function shelfScopeFromSummary(
  shelf: Pick<ShelfSummary, "ownerType" | "canEdit">,
): ShelfScope {
  if (shelf.ownerType === "group") return "group";
  return shelf.canEdit ? "personal" : "shared";
}

export function shelfScopeFromBreadcrumbState(state: unknown): ShelfScope | undefined {
  const trail = readIncomingBreadcrumbTrail(state);
  if (!trail) return undefined;
  return shelfScopePresentations.find(({ label, icon, id }) => {
    const expectedPath = shelfScopePath(id);
    return trail.some((item) => item.label === label && item.icon === icon && item.to === expectedPath);
  })?.id;
}

export function validBreadcrumbStateForShelf(
  state: unknown,
  shelf: Pick<ShelfSummary, "ownerType" | "canEdit">,
): unknown {
  const incoming = readIncomingBreadcrumbTrail(state);
  if (!incoming) return undefined;
  const incomingScope = shelfScopeFromBreadcrumbState(state);
  if (incomingScope && incomingScope !== shelfScopeFromSummary(shelf)) return undefined;
  return state;
}
