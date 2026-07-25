import type { LibrarySeries } from "@second-pass/spl-api";
import { Link } from "react-router-dom";

import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import { BookCoverPreviewStripComponent } from "../../../shared/books/BookCoverPreviewStripComponent";
import { libraryEntityBreadcrumbs, libraryEntityEditPath, libraryEntityNavigationState } from "../authorSeriesLifecycle";
import { previewBooksForLibrary, selectedLibraryContextNavigationState } from "../libraryPresentation";
import { bookCountLabel } from "./AuthorRowComponent";

export function SeriesRowComponent({ series, libraryPath, contextPath, canEdit = false }: { series: LibrarySeries; libraryPath: string; contextPath: string; canEdit?: boolean }) {
  return <article className="library-axis-row-component">
    <div className="library-axis-row-component__identity">
      <div className="library-axis-row-component__heading">
        <h2><Link to={contextPath} state={selectedLibraryContextNavigationState({ kind: "series", id: series.id, name: series.name })}>{series.name}</Link></h2>
        {canEdit ? <Link
          className="icon-button library-axis-row-component__edit"
          to={libraryEntityEditPath("series", series.id)}
          state={libraryEntityNavigationState({
            breadcrumbs: libraryEntityBreadcrumbs("series", "edit", series.name, libraryPath),
            returnTo: libraryPath,
          })}
          aria-label={`Edit ${series.name}`}
          title={`Edit ${series.name}`}
        ><MaterialIcon name="edit" /></Link> : null}
      </div>
      <span>{bookCountLabel(series.bookCount)}</span>
    </div>
    <BookCoverPreviewStripComponent books={previewBooksForLibrary(series.previewBooks, libraryPath)} />
  </article>;
}
