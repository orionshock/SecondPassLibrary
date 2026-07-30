import type { FormEvent } from "react";
import type { MarginaliaSessionListItem, Page } from "@second-pass/spl-api";

import { Button, ErrorPanel } from "../../../components/ui";
import { PaginatedListFrameComponent } from "../../../shared/pagination/PaginatedListFrameComponent";
import { SessionSummaryRowComponent } from "../components/SessionSummaryRowComponent";
import type { MarginaliaStatusFilter } from "../marginaliaQuery";

export function MarginaliaSessionsPageRegion({ page, pageNumber, pageSize, search, status, loading, error, onSearchChange, onSearch, onStatusChange, onPageChange, onPageSizeChange, onRetry }: {
  page?: Page<MarginaliaSessionListItem>;
  pageNumber: number;
  pageSize: number;
  search: string;
  status: MarginaliaStatusFilter;
  loading: boolean;
  error?: Error;
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
    <section className="marginalia-controls" aria-label="Reading session filters">
      <form role="search" onSubmit={submit}>
        <label htmlFor="marginalia-search">Search</label>
        <input id="marginalia-search" type="search" value={search} placeholder="Session, notes, or available Book..." onChange={(event) => onSearchChange(event.target.value)} />
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
    <ReadingSessionResults page={page} pageNumber={pageNumber} pageSize={pageSize} hasFilters={Boolean(search || status !== "all")} loading={loading} error={error} onPageChange={onPageChange} onPageSizeChange={onPageSizeChange} onRetry={onRetry} />
  </div>;
}

function ReadingSessionResults({ page, pageNumber, pageSize, hasFilters, loading, error, onPageChange, onPageSizeChange, onRetry }: {
  page?: Page<MarginaliaSessionListItem>;
  pageNumber: number;
  pageSize: number;
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
        ? <div className="marginalia-empty"><p>No reading sessions found.</p>{hasFilters ? <p className="muted">Try clearing the search or status filter.</p> : <p className="muted">Your reading history will appear here.</p>}</div>
        : <div className="marginalia-session-rows">{page.items.map((session) => <SessionSummaryRowComponent key={session.id} session={session} />)}</div>}
    </PaginatedListFrameComponent>
  </section>;
}
