import type { LibrarySeries } from "@second-pass/spl-api";

import { previewBooksForLibrary, selectedLibraryContextNavigationState } from "../libraryPresentation";
import { bookCountLabel } from "./AuthorRow";
import { LibraryEntityRow } from "./LibraryEntityRow";

export function SeriesRow({ series, libraryPath, contextPath }: { series: LibrarySeries; libraryPath: string; contextPath: string }) {
  return <LibraryEntityRow
    title={series.name}
    subtitle={bookCountLabel(series.bookCount)}
    href={contextPath}
    navigationState={selectedLibraryContextNavigationState({ kind: "series", id: series.id, name: series.name })}
    previewBooks={previewBooksForLibrary(series.previewBooks, libraryPath)}
  />;
}
