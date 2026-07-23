import { PageHeader } from "../../../components/ui";
import type { LibraryView } from "../libraryQuery";

const axes: readonly { view: LibraryView; label: string }[] = [
  { view: "books", label: "Books" },
  { view: "authors", label: "Authors" },
  { view: "series", label: "Series" },
];

export function LibraryAxesPageRegion({ activeView, onViewChange }: {
  activeView: LibraryView;
  onViewChange: (view: LibraryView) => void;
}) {
  return <div className="library-heading">
    <PageHeader title="Library" />
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
