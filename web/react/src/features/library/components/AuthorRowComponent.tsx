import type { LibraryAuthor } from "@second-pass/spl-api";
import { Link } from "react-router-dom";

import { BookCoverPreviewStripComponent } from "../../../shared/books/BookCoverPreviewStripComponent";
import { previewBooksForLibrary, selectedLibraryContextNavigationState } from "../libraryPresentation";

export function AuthorRowComponent({ author, libraryPath, contextPath }: { author: LibraryAuthor; libraryPath: string; contextPath: string }) {
  return <article className="library-axis-row-component">
    <div className="library-axis-row-component__identity">
      <h2><Link to={contextPath} state={selectedLibraryContextNavigationState({ kind: "author", id: author.id, name: author.name })}>{author.name}</Link></h2>
      <span>{bookCountLabel(author.bookCount)}</span>
    </div>
    <BookCoverPreviewStripComponent books={previewBooksForLibrary(author.previewBooks, libraryPath)} />
  </article>;
}

export function bookCountLabel(count: number): string {
  return `${count} ${count === 1 ? "Book" : "Books"}`;
}
