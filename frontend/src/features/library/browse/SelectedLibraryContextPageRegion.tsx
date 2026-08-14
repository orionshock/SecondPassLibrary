import { Link } from "react-router";
import { Button, ErrorPanel } from "../../../components/UiPrimitives";
import { libraryEntityBreadcrumbs, libraryEntityEditPath, libraryEntityNavigationState } from "../authorSeriesLifecycle";
import type { LibrarySelectedContextKind } from "../libraryQuery";
import { ClampedLibraryText } from "./ClampedLibraryText";

export function SelectedLibraryContextPageRegion({ kind, entityId, name, blurb, bookCount, loading = false, unavailable = false, error, canEdit = false, returnTo, onRetry }: {
  kind: LibrarySelectedContextKind;
  entityId?: string;
  name?: string;
  blurb?: string;
  bookCount?: number;
  loading?: boolean;
  unavailable?: boolean;
  error?: Error;
  canEdit?: boolean;
  returnTo?: string;
  onRetry?: () => void;
}) {
  const entityLabel = kind === "author" ? "Author" : "Series";
  const title = unavailable ? `${entityLabel} unavailable` : name || entityLabel;

  return <header className="selected-library-context-region">
    <div className="selected-library-context-region__identity">
      <div className="selected-library-context-region__title">
        <h2>{title}</h2>
        {bookCount !== undefined ? <span className="muted">({bookCount} {bookCount === 1 ? "Book" : "Books"})</span> : null}
      </div>
      {blurb && !unavailable ? <ClampedLibraryText text={blurb} /> : null}
      {loading ? <p className="muted" aria-live="polite">Loading details...</p> : null}
      {unavailable ? <p className="muted">Selected context not found or unavailable.</p> : null}
      {error ? <div className="selected-library-context-region__error"><ErrorPanel>{error.message}</ErrorPanel>{onRetry ? <Button type="button" onClick={onRetry}>Retry</Button> : null}</div> : null}
    </div>
    <div className="selected-library-context-region__actions">
      {canEdit && entityId && !unavailable ? <Link
        className="button button--secondary"
        to={libraryEntityEditPath(kind, entityId)}
        state={libraryEntityNavigationState({
          breadcrumbs: libraryEntityBreadcrumbs(kind, "edit", name, entityId),
          returnTo,
        })}
      >Edit</Link> : null}
    </div>
  </header>;
}
