import { Link } from "react-router";

import { BookCoverComponent } from "./BookCoverComponent";

export interface BookCoverPreviewItem {
  id: string;
  title: string;
  coverUrl: string | null;
  href: string;
  navigationState?: unknown;
}

export function BookCoverPreviewStripComponent({ books }: { books: readonly BookCoverPreviewItem[] }) {
  if (books.length === 0) return null;
  return <div className="book-cover-preview-strip-component" aria-label="Book previews">
    {books.slice(0, 6).map((book) => <Link
      key={book.id}
      to={book.href}
      state={book.navigationState}
      aria-label={`Open ${book.title}`}
      title={book.title}
    ><BookCoverComponent coverUrl={book.coverUrl} title={book.title} /></Link>)}
  </div>;
}
