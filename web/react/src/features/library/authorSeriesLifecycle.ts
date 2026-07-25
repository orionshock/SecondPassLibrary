import { breadcrumbNavigationState, type BreadcrumbItem } from "../../app/navigation/breadcrumbs";

export type LibraryEntityKind = "author" | "series";
export type LibraryEntityEditMode = "new" | "edit";

export function libraryEntityAxisPath(kind: LibraryEntityKind): string {
  return kind === "author" ? "/library?view=authors" : "/library?view=series";
}

export function libraryEntityNewPath(kind: LibraryEntityKind): string {
  return kind === "author" ? "/library/authors/new" : "/library/series/new";
}

export function libraryEntityEditPath(kind: LibraryEntityKind, id: string): string {
  const axis = kind === "author" ? "authors" : "series";
  return `/library/${axis}/${encodeURIComponent(id)}/edit`;
}

export function libraryEntityContextPath(kind: LibraryEntityKind, id: string): string {
  const view = kind === "author" ? "authors" : "series";
  const context = kind === "author" ? "author" : "series";
  return `/library?view=${view}&${context}=${encodeURIComponent(id)}`;
}

export function libraryEntityBreadcrumbs(
  kind: LibraryEntityKind,
  mode: LibraryEntityEditMode,
  name?: string,
  entityId?: string,
  axisPath = libraryEntityAxisPath(kind),
): BreadcrumbItem[] {
  const axis = kind === "author" ? "Authors" : "Series";
  if (mode === "new") {
    return [{ label: "Library", to: "/library", resetTrail: true }, { label: axis, to: axisPath, resetTrail: true }, { label: `New ${titleKind(kind)}` }];
  }
  return [
    { label: "Library", to: "/library", resetTrail: true },
    { label: axis, to: axisPath, resetTrail: true },
    { label: name?.trim() || titleKind(kind), ...(entityId ? { to: libraryEntityContextPath(kind, entityId) } : {}) },
    { label: "Edit" },
  ];
}

export function libraryEntityNavigationState({
  breadcrumbs,
  returnTo,
  successMessage,
}: {
  breadcrumbs: readonly BreadcrumbItem[];
  returnTo?: string;
  successMessage?: string;
}) {
  return {
    ...breadcrumbNavigationState(breadcrumbs),
    ...(isSafeInternalPath(returnTo) ? { libraryEntityReturnTo: returnTo } : {}),
    ...(successMessage ? { libraryEntitySuccessMessage: successMessage } : {}),
  };
}

export function readLibraryEntityReturnTo(state: unknown): string | undefined {
  if (!isRecord(state)) return undefined;
  return isSafeInternalPath(state.libraryEntityReturnTo) ? state.libraryEntityReturnTo : undefined;
}

export function readLibraryEntitySuccessMessage(state: unknown): string | undefined {
  if (!isRecord(state) || typeof state.libraryEntitySuccessMessage !== "string") return undefined;
  const message = state.libraryEntitySuccessMessage.trim();
  return message && message.length <= 160 ? message : undefined;
}

export function titleKind(kind: LibraryEntityKind): "Author" | "Series" {
  return kind === "author" ? "Author" : "Series";
}

function isSafeInternalPath(value: unknown): value is string {
  return typeof value === "string"
    && value.length <= 2048
    && /^\/(?!\/)[^\u0000-\u001f]*$/.test(value);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
