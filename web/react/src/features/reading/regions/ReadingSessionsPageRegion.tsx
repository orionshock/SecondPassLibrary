import type { FormEvent } from "react";
import type { Page, ReadingSessionSummary } from "@second-pass/spl-api";

import { Button, ErrorPanel } from "../../../components/ui";
import { PaginatedListFrameComponent } from "../../../shared/pagination/PaginatedListFrameComponent";
import { SessionSummaryRowComponent } from "../components/SessionSummaryRowComponent";
import type { ReadingStatusFilter } from "../readingQuery";

export function ReadingSessionsPageRegion({ page, pageNumber, pageSize, search, status, loading, error, onSearchChange, onSearch, onStatusChange, onPageChange, onPageSizeChange, onRetry }: {
  page?: Page<ReadingSessionSummary>;
  pageNumber: number;
  pageSize: number;
  search: string;
  status: ReadingStatusFilter;
  loading: boolean;
  error?: Error;
  onSearchChange: (value: string) => void;
  onSearch: () => void;
  onStatusChange: (value: ReadingStatusFilter) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSearch();
  }

  return <div className="reading-page">
    <section className="reading-controls" aria-label="Reading session filters">
      <form role="search" onSubmit={submit}>
        <label htmlFor="reading-search">Search</label>
        <input id="reading-search" type="search" value={search} placeholder="Session, notes, or available Book..." onChange={(event) => onSearchChange(event.target.value)} />
        <Button type="submit">Search</Button>
      </form>
      <label className="reading-status-filter" htmlFor="reading-status">Status
        <select id="reading-status" value={status} onChange={(event) => onStatusChange(event.target.value as ReadingStatusFilter)}>
          <option value="all">All</option>
          <option value="active">Active</option>
          <option value="historical">Historical</option>
        </select>
      </label>
    </section>
    <ReadingSessionResults page={page} pageNumber={pageNumber} pageSize={pageSize} hasFilters={Boolean(search || status !== "all")} loading={loading} error={error} onPageChange={onPageChange} onPageSizeChange={onPageSizeChange} onRetry={onRetry} />
  </div>;
}

function ReadingSessionResults({ page, pageNumber, pageSize, hasFilters, loading, error, onPageChange, onPageSizeChange, onRetry }: {
  page?: Page<ReadingSessionSummary>;
  pageNumber: number;
  pageSize: number;
  hasFilters: boolean;
  loading: boolean;
  error?: Error;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
}) {
  if (!page && loading) return <section className="reading-state" aria-live="polite" aria-busy="true">Loading reading sessions...</section>;
  if (!page && error) return <section className="reading-state"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></section>;
  if (!page) return null;

  return <section className={`reading-results${loading ? " reading-results--loading" : ""}`} aria-busy={loading}>
    {error ? <div className="reading-inline-error"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></div> : null}
    <PaginatedListFrameComponent page={pageNumber} pageSize={pageSize} count={page.count} hasPrevious={Boolean(page.previous)} hasNext={Boolean(page.next)} itemLabel="Reading sessions" onPageChange={onPageChange} onPageSizeChange={onPageSizeChange}>
      {page.items.length === 0
        ? <div className="reading-empty"><p>No reading sessions found.</p>{hasFilters ? <p className="muted">Try clearing the search or status filter.</p> : <p className="muted">Your reading history will appear here.</p>}</div>
        : <div className="reading-session-rows">{page.items.map((session) => <SessionSummaryRowComponent key={session.id} session={session} />)}</div>}
    </PaginatedListFrameComponent>
  </section>;
}
