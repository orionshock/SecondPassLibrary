import type { LibraryAuthor } from "@second-pass/spl-api";

import { previewBooksForLibrary, selectedLibraryContextNavigationState } from "../libraryPresentation";
import { LibraryEntityRow } from "./LibraryEntityRow";

export function AuthorRow({ author, libraryPath, contextPath }: { author: LibraryAuthor; libraryPath: string; contextPath: string }) {
  return <LibraryEntityRow
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
