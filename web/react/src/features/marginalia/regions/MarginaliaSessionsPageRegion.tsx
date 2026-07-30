import type {
  MarginaliaBookReference,
  MarginaliaBookSummary,
  MarginaliaSessionListItem,
  MarginaliaSessionSummary,
  Page,
} from "@second-pass/spl-api";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";

import { Button, ErrorPanel } from "../../../components/ui";
import { CompactBookRowComponent } from "../../../shared/books/CompactBookRowComponent";
import { PaginatedListFrameComponent } from "../../../shared/pagination/PaginatedListFrameComponent";
import { SessionSummaryRowComponent } from "../components/SessionSummaryRowComponent";
import type { MarginaliaStatusFilter } from "../marginaliaQuery";

type SessionRow = MarginaliaSessionListItem | MarginaliaSessionSummary;

export function MarginaliaSessionsPageRegion({
  page,
  pageNumber,
  pageSize,
  search,
  status,
  loading,
  error,
  bookContext,
  onBackToBooks,
  onSearchChange,
  onSearch,
  onStatusChange,
  onPageChange,
  onPageSizeChange,
  onRetry,
}: {
  page?: Page<SessionRow>;
  pageNumber: number;
  pageSize: number;
  search: string;
  status: MarginaliaStatusFilter;
  loading: boolean;
  error?: Error;
  bookContext?: MarginaliaBookSummary;
  onBackToBooks?: () => void;
  onSearchChange: (value: string) => void;
  onSearch: () => void;
  onStatusChange: (value: MarginaliaStatusFilter) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSearch();
  }

  return <div className="marginalia-page">
    {bookContext ? <SelectedBookContextComponent book={bookContext} onBack={onBackToBooks} /> : onBackToBooks ? <div className="marginalia-selected-book__fallback"><Button type="button" size="small" tone="secondary" onClick={onBackToBooks}>Back to Books</Button></div> : null}
    <section className="marginalia-controls" aria-label={bookContext ? "Selected Book session filters" : "Reading session filters"}>
      <form role="search" onSubmit={submit}>
        <label htmlFor="marginalia-search">Search</label>
        <input
          id="marginalia-search"
          type="search"
          value={search}
          placeholder={bookContext ? "Session name or notes..." : "Session, notes, or Book..."}
          onChange={(event) => onSearchChange(event.target.value)}
        />
        <Button type="submit">Search</Button>
      </form>
      <label className="marginalia-status-filter" htmlFor="marginalia-status">Status
        <select id="marginalia-status" value={status} onChange={(event) => onStatusChange(event.target.value as MarginaliaStatusFilter)}>
          <option value="all">All</option>
          <option value="active">Active</option>
          <option value="closed">Closed</option>
        </select>
      </label>
    </section>
    <ReadingSessionResults
      page={page}
      pageNumber={pageNumber}
      pageSize={pageSize}
      bookContext={bookContext}
      hasFilters={Boolean(search || status !== "all")}
      loading={loading}
      error={error}
      onPageChange={onPageChange}
      onPageSizeChange={onPageSizeChange}
      onRetry={onRetry}
    />
  </div>;
}

function SelectedBookContextComponent({ book, onBack }: { book: MarginaliaBookSummary; onBack?: () => void }) {
  return <section className="marginalia-selected-book" aria-label="Selected Marginalia Book">
    <CompactBookRowComponent
      book={book}
      details={<p className="marginalia-book-facts"><span>{formatCount(book.sessionCount, "Session")}</span><span>{book.activeSessionCount} active</span></p>}
      actions={<div className="marginalia-selected-book__actions">
        {book.canOpen ? <Link className="button button--small button--secondary" to={`/library/books/${encodeURIComponent(book.id)}`}>View Book</Link> : null}
        {onBack ? <Button type="button" size="small" tone="secondary" onClick={onBack}>Back to Books</Button> : null}
      </div>}
    />
  </section>;
}

function ReadingSessionResults({ page, pageNumber, pageSize, bookContext, hasFilters, loading, error, onPageChange, onPageSizeChange, onRetry }: {
  page?: Page<SessionRow>;
  pageNumber: number;
  pageSize: number;
  bookContext?: MarginaliaBookSummary;
  hasFilters: boolean;
  loading: boolean;
  error?: Error;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
}) {
  if (!page && loading) return <section className="marginalia-state" aria-live="polite" aria-busy="true">Loading reading sessions...</section>;
  if (!page && error) return <section className="marginalia-state"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></section>;
  if (!page) return null;

  return <section className={`marginalia-results${loading ? " marginalia-results--loading" : ""}`} aria-busy={loading}>
    {error ? <div className="marginalia-inline-error"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></div> : null}
    <PaginatedListFrameComponent page={pageNumber} pageSize={pageSize} count={page.count} hasPrevious={Boolean(page.previous)} hasNext={Boolean(page.next)} itemLabel="Reading sessions" onPageChange={onPageChange} onPageSizeChange={onPageSizeChange}>
      {page.items.length === 0
        ? <div className="marginalia-empty"><p>{bookContext ? "No reading sessions match for this Book." : "No reading sessions found."}</p>{hasFilters ? <p className="muted">Try clearing the search or status filter.</p> : <p className="muted">{bookContext ? "This Book has no Sessions in the selected status." : "Your reading history will appear here."}</p>}</div>
        : <div className="marginalia-session-rows">{page.items.map((session) => <SessionSummaryRowComponent key={session.id} session={session} book={bookReference(session, bookContext)} />)}</div>}
    </PaginatedListFrameComponent>
  </section>;
}

function bookReference(session: SessionRow, context?: MarginaliaBookSummary): MarginaliaBookReference {
  if (context) return { id: context.id, title: context.title, coverUrl: context.coverUrl, canOpen: context.canOpen };
  if ("book" in session) return session.book;
  throw new Error("A Session row requires bounded Book context.");
}

function formatCount(count: number, singular: string): string {
  return `${count} ${singular}${count === 1 ? "" : "s"}`;
}
