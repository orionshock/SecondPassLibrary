import type { BookDetail } from "@second-pass/spl-api";
import { Link } from "react-router-dom";

import { BookCoverComponent } from "../../../shared/books/BookCoverComponent";
import { selectedLibraryContextNavigationState } from "../libraryPresentation";
import { bookSeriesDisplay, formatBookPublishedDate } from "../bookDetailPresentation";

export function BookDetailHeroPageRegion({ book, canEdit = false, editNavigationState }: { book: BookDetail; canEdit?: boolean; editNavigationState?: unknown }) {
  const publishedDate = formatBookPublishedDate(book);
  const facts = [book.publisher, book.language, publishedDate].filter(Boolean);

  return <section className="book-detail-hero-region" aria-labelledby="book-detail-title">
    <div className="book-detail-hero-region__cover">
      <BookCoverComponent coverUrl={book.coverUrl} title={book.title} />
    </div>
    <div className="book-detail-hero-region__identity">
      <h1 id="book-detail-title">{book.title}</h1>
      {book.subtitle ? <p className="book-detail-hero-region__subtitle">{book.subtitle}</p> : null}
      {book.series ? <p className="book-detail-hero-region__series">
        <Link
          to={`/library?view=series&series=${encodeURIComponent(book.series.id)}`}
          state={selectedLibraryContextNavigationState({ kind: "series", id: book.series.id, name: book.series.name })}
        >{bookSeriesDisplay(book.series)}</Link>
      </p> : null}
      {book.authors.length > 0 ? <p className="book-detail-hero-region__authors">By {book.authors.map((author, index) => <span key={author.id}>
        {index > 0 ? ", " : null}
        <Link
          to={`/library?view=authors&author=${encodeURIComponent(author.id)}`}
          state={selectedLibraryContextNavigationState({ kind: "author", id: author.id, name: author.name })}
        >{author.name}</Link>
      </span>)}</p> : null}
      {facts.length > 0 ? <div className="book-detail-hero-region__facts">
        {book.publisher ? <span>Publisher: {book.publisher}</span> : null}
        {book.language ? <span>Language: {book.language}</span> : null}
        {publishedDate ? <span>Published: {publishedDate}</span> : null}
      </div> : null}
      {book.catalogTags.length > 0 ? <div className="book-detail-hero-region__tags" aria-label="Catalog Tags">
        {book.catalogTags.map((tag) => <span key={tag.id}>{tag.name}</span>)}
      </div> : null}
      {book.description ? <p className="book-detail-hero-region__description">{book.description}</p> : null}
      {book.file?.downloadUrl || !book.file || canEdit ? <div className="book-detail-hero-region__actions">
        {book.file?.downloadUrl ? <a className="button" href={book.file.downloadUrl}>Download EPUB</a> : null}
        {canEdit ? <Link className="button button--secondary" to={`/library/books/${encodeURIComponent(book.id)}/edit`} state={editNavigationState}>Edit Book</Link> : null}
        {!book.file ? <p className="book-detail-hero-region__repair-state">This book’s EPUB file is unavailable.</p> : null}
      </div> : null}
    </div>
  </section>;
}
