import { PageHeader } from "../../../components/UiPrimitives";
import { Link } from "react-router";
import { libraryEntityAxisPath, libraryEntityBreadcrumbs, libraryEntityNavigationState, libraryEntityNewPath } from "../authorSeriesLifecycle";
import type { LibraryView } from "../libraryQuery";

const axes: readonly { view: LibraryView; label: string }[] = [
  { view: "books", label: "Books" },
  { view: "authors", label: "Authors" },
  { view: "series", label: "Series" },
];

export function LibraryAxesPageRegion({ activeView, canManageCatalog = false, onViewChange }: {
  activeView: LibraryView;
  canManageCatalog?: boolean;
  onViewChange: (view: LibraryView) => void;
}) {
  const lifecycleKind = activeView === "authors" ? "author" : activeView === "series" ? "series" : undefined;
  return <div className="library-heading">
    <PageHeader title="Library" />
    <div className="library-axis-bar">
      <div className="library-axes" role="group" aria-label="Library views">
        {axes.map(({ view, label }) => <button
          key={view}
          type="button"
          className={activeView === view ? "active" : ""}
          aria-pressed={activeView === view}
          onClick={() => onViewChange(view)}
        >{label}</button>)}
      </div>
      {canManageCatalog && lifecycleKind ? <Link
        className="button button--secondary library-axis-create-action"
        to={libraryEntityNewPath(lifecycleKind)}
        state={libraryEntityNavigationState({
          breadcrumbs: libraryEntityBreadcrumbs(lifecycleKind, "new"),
          returnTo: libraryEntityAxisPath(lifecycleKind),
        })}
      >New {lifecycleKind === "author" ? "Author" : "Series"}</Link> : null}
    </div>
  </div>;
}
