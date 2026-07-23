import type { LibrarySeries } from "@second-pass/spl-api";

import { BookCoverPreviewStripComponent } from "../../../shared/books/BookCoverPreviewStripComponent";
import { previewBooksForLibrary } from "../libraryPresentation";
import { bookCountLabel } from "./AuthorRowComponent";

export function SeriesRowComponent({ series, libraryPath }: { series: LibrarySeries; libraryPath: string }) {
  return <article className="library-axis-row-component">
    <div className="library-axis-row-component__identity">
      <h2>{series.name}</h2>
      <span>{bookCountLabel(series.bookCount)}</span>
    </div>
    <BookCoverPreviewStripComponent books={previewBooksForLibrary(series.previewBooks, libraryPath)} />
  </article>;
}
