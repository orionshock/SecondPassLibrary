import type { CompactBook } from "@second-pass/spl-api";
import { Link } from "react-router-dom";

import { breadcrumbNavigationState } from "../../../app/navigation/breadcrumbs";
import { BookCoverComponent } from "../../../shared/books/BookCoverComponent";
import { BookMetadataComponent } from "../../../shared/books/BookMetadataComponent";
import { bookAuthorNames, bookSeriesLabel, visibleCatalogTags } from "../libraryPresentation";
import { bookBrowseDetailBreadcrumbs } from "../bookDetailPresentation";

export function BookRowComponent({ book, libraryPath, contextLabel, parentLibraryPath = libraryPath }: {
  book: CompactBook;
  libraryPath: string;
  contextLabel?: string;
  parentLibraryPath?: string;
}) {
  const detailPath = `/library/books/${encodeURIComponent(book.id)}`;
  const navigationState = breadcrumbNavigationState(bookBrowseDetailBreadcrumbs({
    title: book.title,
    libraryPath,
    contextLabel,
    parentLibraryPath,
  }));
  const { tags, hiddenCount } = visibleCatalogTags(book);

  return <article className="book-row-component">
    <Link className="book-row-component__cover-link" to={detailPath} state={navigationState} aria-label={`Open ${book.title}`}>
      <BookCoverComponent coverUrl={book.coverUrl} title={book.title} />
    </Link>
    <div className="book-row-component__body">
      <h2><Link to={detailPath} state={navigationState}>{book.title}</Link></h2>
      <BookMetadataComponent authors={bookAuthorNames(book)} series={bookSeriesLabel(book)} publisher={book.publisher || undefined} />
      {tags.length > 0 ? <div className="book-row-component__tags" aria-label="Catalog Tags">
        {tags.map((tag) => <span className="book-row-component__tag" key={tag.id}>{tag.name}</span>)}
        {hiddenCount > 0 ? <span className="book-row-component__tag book-row-component__tag--more">+{hiddenCount}</span> : null}
      </div> : null}
    </div>
  </article>;
}
