import type { FormEvent } from "react";

import { Button } from "../../../components/ui";
import { libraryOrderingOptions, type LibraryBookUiOrdering } from "../libraryQuery";

export function LibraryBooksControlsPageRegion({ search, ordering, onSearchChange, onSearch, onOrderingChange }: {
  search: string;
  ordering: LibraryBookUiOrdering;
  onSearchChange: (value: string) => void;
  onSearch: () => void;
  onOrderingChange: (ordering: LibraryBookUiOrdering) => void;
}) {
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); onSearch(); }

  return <section className="library-controls" aria-label="Book controls">
    <form className="library-search" role="search" onSubmit={submit}>
      <label htmlFor="library-search">Search</label>
      <input id="library-search" value={search} placeholder="Book title…" onChange={(event) => onSearchChange(event.target.value)} />
      <Button type="submit">Search</Button>
    </form>
    <label className="library-ordering">Order
      <select aria-label="Book ordering" value={ordering} onChange={(event) => onOrderingChange(event.target.value as LibraryBookUiOrdering)}>
        {libraryOrderingOptions.map(({ value, label }) => <option key={value} value={value}>{label}</option>)}
      </select>
    </label>
  </section>;
}
