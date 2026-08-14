import type { CompactBook, Page } from "@second-pass/spl-api";
import type { FormEvent } from "react";

import { breadcrumbNavigationState } from "../../../app/navigation/breadcrumbs";
import { Button, ErrorPanel } from "../../../components/ui";
import { CompactBookRow } from "../../../shared/books/CompactBookRow";
import { Pager } from "../../../shared/pagination/Pager";
import { groupBookBreadcrumbs } from "../groupsBreadcrumbs";

export function GroupBookCandidatesPageRegion({ groupId, groupName, isPublicGroup, search, page, pageNumber, pageSize, loading, error, pendingBookId, controlsDisabled, onSearchChange, onSearch, onAdd, onPageChange, onPageSizeChange, onRetry }: {
  groupId: string;
  groupName: string;
  isPublicGroup?: boolean;
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

  return <section className="group-book-candidates-region" aria-label="Add group books">
    <form className="group-edit-book-search" role="search" onSubmit={submit}>
      <label htmlFor="group-add-books-search">Search</label>
      <input id="group-add-books-search" value={search} placeholder="Search books..." onChange={(event) => onSearchChange(event.target.value)} />
      <Button type="submit">Search</Button>
    </form>
    {!page && !loading && !error ? <p className="muted">Search for books to add.</p> : null}
    {!page && loading ? <div className="group-edit-section-state" aria-live="polite" aria-busy="true">Searching...</div> : null}
    {!page && error ? <div className="group-edit-section-state"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></div> : null}
    {page ? <div className="group-book-candidates" aria-busy={loading}>
      {error ? <div className="groups-inline-error"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></div> : null}
      {page.items.length === 0 ? <p className="muted">No matching books.</p> : <div className="group-book-rows">
        {page.items.map((book) => <CompactBookRow
          key={book.id}
          book={book}
          detailPath={`/library/books/${encodeURIComponent(book.id)}`}
          navigationState={breadcrumbNavigationState(groupBookBreadcrumbs(groupId, groupName, book.title, undefined, isPublicGroup))}
          actions={<Button type="button" disabled={controlsDisabled || Boolean(pendingBookId)} onClick={() => onAdd(book.id)}>
            {pendingBookId === book.id ? "Adding..." : "Add"}
          </Button>}
        />)}
      </div>}
      <Pager page={pageNumber} pageSize={pageSize} count={page.count} hasPrevious={Boolean(page.previous)} hasNext={Boolean(page.next)} itemLabel="Books" onPageChange={onPageChange} onPageSizeChange={onPageSizeChange} />
    </div> : null}
  </section>;
}
