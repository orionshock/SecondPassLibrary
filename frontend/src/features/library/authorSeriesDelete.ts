import { confirmDangerousAction } from "../../shared/confirmations/confirmDangerousAction";
import { titleKind, type LibraryEntityKind } from "./authorSeriesLifecycle";

export function confirmAuthorSeriesDelete(
  kind: LibraryEntityKind,
  name: string,
  confirm: (message: string) => boolean = window.confirm,
): boolean {
  const entity = titleKind(kind);
  return confirmDangerousAction(
    `Permanently delete ${entity} “${name}”? This cannot be undone. Books will not be detached, reassigned, or merged.`,
    confirm,
  );
}

export function isAttachedBookConflict(error: unknown, kind: LibraryEntityKind): boolean {
  if (!error || typeof error !== "object") return false;
  const expectedCode = kind === "author" ? "author_has_books" : "series_has_books";
  return "status" in error && error.status === 409 && "code" in error && error.code === expectedCode;
}
