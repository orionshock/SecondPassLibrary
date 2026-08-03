import type { LibraryAuthor } from "@second-pass/spl-api";

import { previewBooksForLibrary, selectedLibraryContextNavigationState } from "../libraryPresentation";
import { LibraryEntityRowComponent } from "./LibraryEntityRowComponent";

export function AuthorRowComponent({ author, libraryPath, contextPath }: { author: LibraryAuthor; libraryPath: string; contextPath: string }) {
  return <LibraryEntityRowComponent
    title={author.name}
    subtitle={bookCountLabel(author.bookCount)}
    href={contextPath}
    navigationState={selectedLibraryContextNavigationState({ kind: "author", id: author.id, name: author.name })}
    previewBooks={previewBooksForLibrary(author.previewBooks, libraryPath)}
  />;
}

export function bookCountLabel(count: number): string {
  return `${count} ${count === 1 ? "Book" : "Books"}`;
}
