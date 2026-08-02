import { Link } from "react-router";

import { BookCoverPreviewStripComponent, type BookCoverPreviewItem } from "../../../shared/books/BookCoverPreviewStripComponent";

export function LibraryEntityRowComponent({
  title,
  subtitle,
  href,
  navigationState,
  previewBooks,
}: {
  title: string;
  subtitle: string;
  href: string;
  navigationState?: unknown;
  previewBooks: readonly BookCoverPreviewItem[];
}) {
  return <article className="library-axis-row-component">
    <div className="library-axis-row-component__identity">
      <h2><Link to={href} state={navigationState}>{title}</Link></h2>
      <span>{subtitle}</span>
    </div>
    <BookCoverPreviewStripComponent books={previewBooks} />
  </article>;
}
