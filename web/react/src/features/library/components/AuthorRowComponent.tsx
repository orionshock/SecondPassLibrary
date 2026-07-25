import type { LibraryAuthor } from "@second-pass/spl-api";
import { Link } from "react-router-dom";

import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import { BookCoverPreviewStripComponent } from "../../../shared/books/BookCoverPreviewStripComponent";
import { libraryEntityBreadcrumbs, libraryEntityEditPath, libraryEntityNavigationState } from "../authorSeriesLifecycle";
import { previewBooksForLibrary, selectedLibraryContextNavigationState } from "../libraryPresentation";

export function AuthorRowComponent({ author, libraryPath, contextPath, canEdit = false }: { author: LibraryAuthor; libraryPath: string; contextPath: string; canEdit?: boolean }) {
  return <article className="library-axis-row-component">
    <div className="library-axis-row-component__identity">
      <div className="library-axis-row-component__heading">
        <h2><Link to={contextPath} state={selectedLibraryContextNavigationState({ kind: "author", id: author.id, name: author.name })}>{author.name}</Link></h2>
        {canEdit ? <Link
          className="icon-button library-axis-row-component__edit"
          to={libraryEntityEditPath("author", author.id)}
          state={libraryEntityNavigationState({
            breadcrumbs: libraryEntityBreadcrumbs("author", "edit", author.name, libraryPath),
            returnTo: libraryPath,
          })}
          aria-label={`Edit ${author.name}`}
          title={`Edit ${author.name}`}
        ><MaterialIcon name="edit" /></Link> : null}
      </div>
      <span>{bookCountLabel(author.bookCount)}</span>
    </div>
    <BookCoverPreviewStripComponent books={previewBooksForLibrary(author.previewBooks, libraryPath)} />
  </article>;
}

export function bookCountLabel(count: number): string {
  return `${count} ${count === 1 ? "Book" : "Books"}`;
}
