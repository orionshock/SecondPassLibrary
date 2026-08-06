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
  const hasPreviews = previewBooks.length > 0;
  return <article className={`library-axis-row-component compact-cover-preview-row${hasPreviews ? "" : " compact-cover-preview-row--without-previews"}`}>
    <div className="library-axis-row-component__identity compact-cover-preview-row__primary">
      <h2><Link to={href} state={navigationState}>{title}</Link></h2>
      <span>{subtitle}</span>
    </div>
    {hasPreviews ? <BookCoverPreviewStripComponent books={previewBooks} /> : null}
  </article>;
}
