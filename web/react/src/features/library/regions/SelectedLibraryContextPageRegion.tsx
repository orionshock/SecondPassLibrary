import { Button } from "../../../components/ui";
import type { LibrarySelectedContextKind } from "../libraryQuery";

export function SelectedLibraryContextPageRegion({ kind, name, bookCount, onBack }: {
  kind: LibrarySelectedContextKind;
  name?: string;
  bookCount?: number;
  onBack: () => void;
}) {
  const owningAxis = kind === "author" ? "Authors" : "Series";
  const title = name
    ? kind === "author" ? `Books by ${name}` : `Books in ${name}`
    : kind === "author" ? "Author Books" : "Series Books";

  return <header className="selected-library-context-region">
    <div>
      <h2>{title}</h2>
      {bookCount !== undefined ? <p className="muted">{bookCount} {bookCount === 1 ? "Book" : "Books"}</p> : null}
    </div>
    <Button type="button" onClick={onBack}>Back to {owningAxis}</Button>
  </header>;
}
