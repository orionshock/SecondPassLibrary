import type { MarginaliaBookSummary, Page } from "@second-pass/spl-api";
import type { FormEvent } from "react";
import { Link } from "react-router";

import { Button, ErrorPanel } from "../../../components/ui";
import { CompactBookRow } from "../../../shared/books/CompactBookRow";
import { PaginatedListFrame } from "../../../shared/pagination/PaginatedListFrame";

export function MarginaliaBooksPageRegion({ page, pageNumber, pageSize, search, loading, error, bookPath, onSearchChange, onSearch, onPageChange, onPageSizeChange, onRetry }: {
  page?: Page<MarginaliaBookSummary>;
  pageNumber: number;
  pageSize: number;
  search: string;
  loading: boolean;
  error?: Error;
  bookPath: (bookId: string) => string;
  onSearchChange: (value: string) => void;
  onSearch: () => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSearch();
  }

  return <div className="marginalia-page">
    <section className="marginalia-controls" aria-label="Marginalia Book filters">
      <form role="search" onSubmit={submit}>
        <label htmlFor="marginalia-book-search">Search</label>
        <input id="marginalia-book-search" type="search" value={search} placeholder="Title, author, or series..." onChange={(event) => onSearchChange(event.target.value)} />
        <Button type="submit">Search</Button>
      </form>
    </section>
    <BookResults page={page} pageNumber={pageNumber} pageSize={pageSize} searching={Boolean(search)} loading={loading} error={error} bookPath={bookPath} onPageChange={onPageChange} onPageSizeChange={onPageSizeChange} onRetry={onRetry} />
  </div>;
}

function BookResults({ page, pageNumber, pageSize, searching, loading, error, bookPath, onPageChange, onPageSizeChange, onRetry }: {
  page?: Page<MarginaliaBookSummary>;
  pageNumber: number;
  pageSize: number;
  searching: boolean;
  loading: boolean;
  error?: Error;
  bookPath: (bookId: string) => string;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
}) {
  if (!page && loading) return <section className="marginalia-state" aria-live="polite" aria-busy="true">Loading Marginalia Books...</section>;
  if (!page && error) return <section className="marginalia-state"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></section>;
  if (!page) return null;

  return <section className={`marginalia-results${loading ? " marginalia-results--loading" : ""}`} aria-label="Marginalia Books" aria-busy={loading}>
    {error ? <div className="marginalia-inline-error"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></div> : null}
    <PaginatedListFrame page={pageNumber} pageSize={pageSize} count={page.count} hasPrevious={Boolean(page.previous)} hasNext={Boolean(page.next)} itemLabel="Books" onPageChange={onPageChange} onPageSizeChange={onPageSizeChange}>
      {page.items.length === 0
        ? <div className="marginalia-empty"><p>{searching ? "No Books with Marginalia match this search." : "No Books with Marginalia found."}</p></div>
        : <div className="marginalia-book-rows">{page.items.map((book) => <CompactBookRow
          key={book.id}
          book={book}
          detailPath={bookPath(book.id)}
          details={<BookMarginaliaFacts book={book} />}
          actions={book.canOpen ? <Link className="button button--small button--secondary" to={`/library/books/${encodeURIComponent(book.id)}`}>View Book</Link> : null}
        />)}</div>}
    </PaginatedListFrame>
  </section>;
}

function BookMarginaliaFacts({ book }: { book: MarginaliaBookSummary }) {
  return <p className="marginalia-book-facts">
    <span>{formatCount(book.sessionCount, "Session")}</span>
    <span>{book.activeSessionCount} active</span>
    <span>Last activity <time dateTime={book.lastActivityAt}>{formatDate(book.lastActivityAt)}</time></span>
  </p>;
}

function formatDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Unknown date";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(parsed);
}

function formatCount(count: number, singular: string): string {
  return `${count} ${singular}${count === 1 ? "" : "s"}`;
}
