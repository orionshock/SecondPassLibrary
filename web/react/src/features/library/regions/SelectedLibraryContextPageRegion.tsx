import { Button } from "../../../components/ui";
import { Link } from "react-router-dom";
import { libraryEntityBreadcrumbs, libraryEntityEditPath, libraryEntityNavigationState } from "../authorSeriesLifecycle";
import type { LibrarySelectedContextKind } from "../libraryQuery";

export function SelectedLibraryContextPageRegion({ kind, entityId, name, bookCount, canEdit = false, returnTo, onBack }: {
  kind: LibrarySelectedContextKind;
  entityId?: string;
  name?: string;
  bookCount?: number;
  canEdit?: boolean;
  returnTo?: string;
  onBack: () => void;
}) {
  const owningAxis = kind === "author" ? "Authors" : "Series";
  const title = name
    ? kind === "author" ? `Books by ${name}` : `Books in ${name}`
    : kind === "author" ? "Author Books" : "Series Books";

  return <header className="selected-library-context-region">
    <div>
      <h2>{title}</h2>
      {bookCount !== undefined ? <p className="muted">{bookCount} {bookCount === 1 ? "Book" : "Books"}</p> : null}
    </div>
    <div className="selected-library-context-region__actions">
      {canEdit && entityId ? <Link
        className="button button--secondary"
        to={libraryEntityEditPath(kind, entityId)}
        state={libraryEntityNavigationState({
          breadcrumbs: libraryEntityBreadcrumbs(kind, "edit", name),
          returnTo,
        })}
      >Edit</Link> : null}
      <Button type="button" onClick={onBack}>Back to {owningAxis}</Button>
    </div>
  </header>;
}
