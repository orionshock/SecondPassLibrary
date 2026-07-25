import { PageHeader } from "../../../components/ui";
import { Link } from "react-router-dom";
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
    <PageHeader title="Library" actions={canManageCatalog && lifecycleKind ? <Link
      className="button button--secondary"
      to={libraryEntityNewPath(lifecycleKind)}
      state={libraryEntityNavigationState({
        breadcrumbs: libraryEntityBreadcrumbs(lifecycleKind, "new"),
        returnTo: libraryEntityAxisPath(lifecycleKind),
      })}
    >New {lifecycleKind === "author" ? "Author" : "Series"}</Link> : undefined} />
    <nav className="library-axes" aria-label="Library views">
      {axes.map(({ view, label }) => <button
        key={view}
        type="button"
        className={activeView === view ? "active" : ""}
        aria-current={activeView === view ? "page" : undefined}
        onClick={() => onViewChange(view)}
      >{label}</button>)}
    </nav>
  </div>;
}
