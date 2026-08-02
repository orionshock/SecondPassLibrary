import type { BookPreview } from "@second-pass/spl-api";
import { Link } from "react-router-dom";

import { breadcrumbNavigationState, type BreadcrumbItem } from "../../../app/navigation/breadcrumbs";
import { BookCoverPreviewStripComponent } from "../../../shared/books/BookCoverPreviewStripComponent";
import {
  libraryEntityAttachedBookBreadcrumbs,
  libraryEntityContextPath,
  titleKind,
  type LibraryEntityKind,
} from "../authorSeriesLifecycle";

export function AuthorSeriesAttachedBooksPageRegion({ kind, entityId, bookCount, books, breadcrumbTrail, editPath }: {
  kind: LibraryEntityKind;
  entityId: string;
  bookCount: number;
  books: readonly BookPreview[];
  breadcrumbTrail: readonly BreadcrumbItem[];
  editPath: string;
}) {
  const entity = titleKind(kind);
  const contextPath = libraryEntityContextPath(kind, entityId);
  const previewBooks = books.slice(0, 6).map((book) => ({
    ...book,
    href: `/library/books/${encodeURIComponent(book.id)}`,
    navigationState: breadcrumbNavigationState(
      libraryEntityAttachedBookBreadcrumbs(breadcrumbTrail, editPath, book.title),
    ),
  }));

  return <section className="author-series-attached-books" aria-labelledby={`${kind}-attached-books-heading`}>
    <div className="author-series-attached-books__heading">
      <div>
        <h2 id={`${kind}-attached-books-heading`}>Attached Books</h2>
        <p className="muted">
          {bookCount === 0
            ? `No Books are attached to this ${entity}.`
            : `Showing ${previewBooks.length} of ${bookCount} attached ${bookCount === 1 ? "Book" : "Books"}.`}
        </p>
      </div>
      {bookCount > 0 ? <Link className="button button--secondary" to={contextPath}>View all attached Books</Link> : null}
    </div>
    <BookCoverPreviewStripComponent books={previewBooks} />
  </section>;
}
