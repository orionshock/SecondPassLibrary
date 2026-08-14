import { Link } from "react-router";

import { BookCover } from "./BookCover";
import { COMPACT_BOOK_COVER_PREVIEW_SOURCE_LIMIT } from "./bookCoverPreview";

export interface BookCoverPreviewItem {
  id: string;
  title: string;
  coverUrl: string | null;
  href: string;
  navigationState?: unknown;
}

export function BookCoverPreviewStrip({ books }: { books: readonly BookCoverPreviewItem[] }) {
  if (books.length === 0) return null;
  return <div className="book-cover-preview-strip-component" aria-label="Book previews">
    {books.slice(0, COMPACT_BOOK_COVER_PREVIEW_SOURCE_LIMIT).map((book) => <Link
      key={book.id}
      to={book.href}
      state={book.navigationState}
      aria-label={`Open ${book.title}`}
      title={book.title}
    ><BookCover coverUrl={book.coverUrl} title={book.title} /></Link>)}
  </div>;
}
