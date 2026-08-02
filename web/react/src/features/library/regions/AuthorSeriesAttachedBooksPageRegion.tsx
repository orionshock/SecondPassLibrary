import type { BookPreview } from "@second-pass/spl-api";
import { Link } from "react-router-dom";

import { breadcrumbNavigationState, type BreadcrumbItem } from "../../../app/navigation/breadcrumbs";
import { Button, ErrorPanel } from "../../../components/ui";
import { BookCoverComponent } from "../../../shared/books/BookCoverComponent";
import {
  libraryEntityAttachedBookBreadcrumbs,
  libraryEntityContextPath,
  titleKind,
  type LibraryEntityKind,
} from "../authorSeriesLifecycle";

export function AuthorSeriesAttachedBooksPageRegion({
  kind,
  entityId,
  bookCount,
  books,
  loadedTotal,
  pending,
  error,
  hasMore,
  breadcrumbTrail,
  editPath,
  onLoadMore,
  onRetry,
}: {
  kind: LibraryEntityKind;
  entityId: string;
  bookCount: number;
  books: readonly BookPreview[];
  loadedTotal: number;
  pending: boolean;
  error?: Error;
  hasMore: boolean;
  breadcrumbTrail: readonly BreadcrumbItem[];
  editPath: string;
  onLoadMore: () => void;
  onRetry: () => void;
}) {
  const entity = titleKind(kind);
  const contextPath = libraryEntityContextPath(kind, entityId);
  const total = loadedTotal || bookCount;
  const complete = !pending && !error && !hasMore;

  return <section className="author-series-attached-books" aria-labelledby={`${kind}-attached-books-heading`}>
    <div className="author-series-attached-books__heading">
      <div>
        <h2 id={`${kind}-attached-books-heading`}>Attached Books</h2>
        <p className="muted">
          {bookCount === 0
            ? `No Books are attached to this ${entity}.`
            : complete
              ? `All ${books.length} attached ${books.length === 1 ? "Book is" : "Books are"} loaded.`
              : `Showing ${books.length} of ${total} attached ${total === 1 ? "Book" : "Books"}.`}
        </p>
      </div>
      {bookCount > 0 ? <Link className="button button--secondary" to={contextPath}>Browse in Library</Link> : null}
    </div>
    {books.length > 0 ? <div className="author-series-attached-books__grid" aria-label={`Attached Books for this ${entity}`}>
      {books.map((book) => <Link
        key={book.id}
        to={`/library/books/${encodeURIComponent(book.id)}`}
        state={breadcrumbNavigationState(
          libraryEntityAttachedBookBreadcrumbs(breadcrumbTrail, editPath, book.title),
        )}
        aria-label={`View ${book.title}`}
        title={book.title}
      ><BookCoverComponent coverUrl={book.coverUrl} title={book.title} /></Link>)}
    </div> : null}
    <div className="author-series-attached-books__status" aria-live="polite">
      {pending ? "Loading attached Books…" : null}
      {error ? <ErrorPanel>{error.message}</ErrorPanel> : null}
    </div>
    <div className="author-series-attached-books__actions">
      {error ? <Button type="button" onClick={onRetry} disabled={pending}>Retry</Button> : null}
      {!error && hasMore ? <Button type="button" onClick={onLoadMore} disabled={pending}>
        {pending ? "Loading…" : "Load more"}
      </Button> : null}
    </div>
  </section>;
}
