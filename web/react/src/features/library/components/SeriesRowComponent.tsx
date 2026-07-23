import type { LibrarySeries } from "@second-pass/spl-api";
import { Link } from "react-router-dom";

import { BookCoverPreviewStripComponent } from "../../../shared/books/BookCoverPreviewStripComponent";
import { previewBooksForLibrary, selectedLibraryContextNavigationState } from "../libraryPresentation";
import { bookCountLabel } from "./AuthorRowComponent";

export function SeriesRowComponent({ series, libraryPath, contextPath }: { series: LibrarySeries; libraryPath: string; contextPath: string }) {
  return <article className="library-axis-row-component">
    <div className="library-axis-row-component__identity">
      <h2><Link to={contextPath} state={selectedLibraryContextNavigationState({ kind: "series", id: series.id, name: series.name })}>{series.name}</Link></h2>
      <span>{bookCountLabel(series.bookCount)}</span>
    </div>
    <BookCoverPreviewStripComponent books={previewBooksForLibrary(series.previewBooks, libraryPath)} />
  </article>;
}
