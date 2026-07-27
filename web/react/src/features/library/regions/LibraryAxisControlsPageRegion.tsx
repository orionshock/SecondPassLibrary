import type { FormEvent } from "react";

import { Button } from "../../../components/ui";
import { OrderMenuComponent } from "../../../shared/forms/OrderMenuComponent";
import { libraryOrderingOptions, type LibrarySelectedContextKind, type LibraryUiOrdering, type LibraryView } from "../libraryQuery";

const labels = {
  books: { region: "Book controls", item: "books", placeholder: "Book title..." },
  authors: { region: "Author controls", item: "authors", placeholder: "Author name..." },
  series: { region: "Series controls", item: "series", placeholder: "Series name..." },
} as const;

export function LibraryAxisControlsPageRegion({ view, selectedContext, search, ordering, onSearchChange, onSearch, onOrderingChange }: {
  view: LibraryView;
  selectedContext?: LibrarySelectedContextKind;
  search: string;
  ordering: LibraryUiOrdering;
  onSearchChange: (value: string) => void;
  onSearch: () => void;
  onOrderingChange: (ordering: LibraryUiOrdering) => void;
}) {
  const copy = selectedContext ? labels.books : labels[view];
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); onSearch(); }

  return <section className="library-controls" aria-label={copy.region}>
    <form className="library-search" role="search" onSubmit={submit}>
      <label htmlFor="library-search">Search</label>
      <input id="library-search" value={search} placeholder={copy.placeholder} onChange={(event) => onSearchChange(event.target.value)} />
      <Button type="submit">Search</Button>
    </form>
    <OrderMenuComponent
      label="Order"
      ariaLabel={`Sort ${copy.item}`}
      value={ordering}
      options={libraryOrderingOptions(view, selectedContext)}
      onChange={onOrderingChange}
    />
  </section>;
}
