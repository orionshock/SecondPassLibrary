import type { CompactBook, Page, ShelfScope } from "@second-pass/spl-api";
import type { FormEvent } from "react";

import { breadcrumbNavigationState } from "../../../app/navigation/breadcrumbs";
import { Button, ErrorPanel } from "../../../components/ui";
import { CompactBookRowComponent } from "../../../shared/books/CompactBookRowComponent";
import { PagerComponent } from "../../../shared/pagination/PagerComponent";
import { shelfBookBreadcrumbs } from "../shelvesBreadcrumbs";

export function ShelfEditAddBooksPageRegion({ shelfId, shelfName, scope, search, page, pageNumber, pageSize, loading, error, pendingBookId, controlsDisabled, onSearchChange, onSearch, onAdd, onPageChange, onPageSizeChange, onRetry }: {
  shelfId: string;
  shelfName: string;
  scope: ShelfScope;
  search: string;
  page?: Page<CompactBook>;
  pageNumber: number;
  pageSize: number;
  loading: boolean;
  error?: Error;
  pendingBookId?: string;
  controlsDisabled?: boolean;
  onSearchChange: (value: string) => void;
  onSearch: () => void;
  onAdd: (bookId: string) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSearch();
  }

  return <section className="shelf-edit-add-books-region" aria-label="Add books">
    <form className="shelf-edit-book-search" role="search" onSubmit={submit}>
      <label htmlFor="shelf-add-books-search">Search</label>
      <input id="shelf-add-books-search" value={search} placeholder="Search books..." onChange={(event) => onSearchChange(event.target.value)} />
      <Button type="submit">Search</Button>
    </form>
    {!page && !loading && !error ? <p className="muted">Search for books to add.</p> : null}
    {!page && loading ? <div className="shelf-edit-section-state" aria-live="polite" aria-busy="true">Searching...</div> : null}
    {!page && error ? <div className="shelf-edit-section-state"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></div> : null}
    {page ? <div className="shelf-edit-candidates" aria-busy={loading}>
      {error ? <div className="shelf-edit-inline-error"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></div> : null}
      {page.items.length === 0 ? <p className="muted">No matching books.</p> : <div className="shelf-edit-book-rows">
        {page.items.map((book) => <CompactBookRowComponent
            key={book.id}
            book={book}
            detailPath={`/library/books/${encodeURIComponent(book.id)}`}
            navigationState={breadcrumbNavigationState(shelfBookBreadcrumbs(scope, shelfId, shelfName, book.title))}
            actions={<Button type="button" disabled={controlsDisabled || Boolean(pendingBookId)} onClick={() => onAdd(book.id)}>
              {pendingBookId === book.id ? "Adding..." : "Add"}
            </Button>}
          />)}
      </div>}
      <PagerComponent page={pageNumber} pageSize={pageSize} count={page.count} hasPrevious={Boolean(page.previous)} hasNext={Boolean(page.next)} itemLabel="Books" onPageChange={onPageChange} onPageSizeChange={onPageSizeChange} />
    </div> : null}
  </section>;
}
