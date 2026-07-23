import type { LibraryAuthor } from "@second-pass/spl-api";

import { BookCoverPreviewStripComponent } from "../../../shared/books/BookCoverPreviewStripComponent";
import { previewBooksForLibrary } from "../libraryPresentation";

export function AuthorRowComponent({ author, libraryPath }: { author: LibraryAuthor; libraryPath: string }) {
  return <article className="library-axis-row-component">
    <div className="library-axis-row-component__identity">
      <h2>{author.name}</h2>
      <span>{bookCountLabel(author.bookCount)}</span>
    </div>
    <BookCoverPreviewStripComponent books={previewBooksForLibrary(author.previewBooks, libraryPath)} />
  </article>;
}

export function bookCountLabel(count: number): string {
  return `${count} ${count === 1 ? "Book" : "Books"}`;
}
