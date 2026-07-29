import type { FormEvent } from "react";
import type { Page, ReadingSessionSummary } from "@second-pass/spl-api";

import { Badge, Button, ErrorPanel, Surface } from "../../../components/ui";
import { BookCoverComponent } from "../../../shared/books/BookCoverComponent";
import { marginaliaSessionDisplayName } from "../../../shared/marginaliaSessionDisplayName";
import { ActionFeedbackComponent } from "../../../shared/feedback/ActionFeedbackComponent";
import type { MutationState } from "../../../shared/feedback/mutationState";
import { PaginatedListFrameComponent } from "../../../shared/pagination/PaginatedListFrameComponent";
import type { MarginaliaStatusFilter } from "../marginaliaQuery";

export function MarginaliaExportPageRegion({ page, pageNumber, pageSize, search, status, loading, loadError, completeState, selectedState, selectedSessionIds, selectedBookCount, includeEmptySessions, onIncludeEmptySessionsChange, onSearchChange, onSearch, onStatusChange, onPageChange, onPageSizeChange, onRetry, onCompleteExport, onSessionSelectionChange, onSelectPage, onClearSelection, onSelectedExport }: {
  page?: Page<ReadingSessionSummary>;
  pageNumber: number;
  pageSize: number;
  search: string;
  status: MarginaliaStatusFilter;
  loading: boolean;
  loadError?: Error;
  completeState: MutationState;
  selectedState: MutationState;
  selectedSessionIds: ReadonlySet<string>;
  selectedBookCount: number;
  includeEmptySessions: boolean;
  onIncludeEmptySessionsChange: (include: boolean) => void;
  onSearchChange: (value: string) => void;
  onSearch: () => void;
  onStatusChange: (value: MarginaliaStatusFilter) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
  onCompleteExport: () => void;
  onSessionSelectionChange: (session: ReadingSessionSummary, selected: boolean) => void;
  onSelectPage: () => void;
  onClearSelection: () => void;
  onSelectedExport: () => void;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSearch();
  }

  return <div className="marginalia-export-page">
    <label className="marginalia-empty-sessions-toggle marginalia-export-empty-sessions"><input type="checkbox" checked={includeEmptySessions} disabled={completeState.pending || selectedState.pending} onChange={(event) => onIncludeEmptySessionsChange(event.target.checked)} />Include empty sessions</label>
    <Surface title="Complete archive">
      <div className="marginalia-export-complete">
        <p>Download all of your reading history, including Sessions tied to Books that are no longer available.</p>
        <div className="marginalia-export-action-row"><ActionFeedbackComponent state={completeState} /><Button type="button" disabled={completeState.pending} onClick={onCompleteExport}>{completeState.pending ? "Preparing..." : "Download complete archive"}</Button></div>
      </div>
    </Surface>

    <section className="marginalia-export-selective" aria-labelledby="marginalia-export-selective-heading">
      <header className="marginalia-export-selective__header">
        <div><h2 id="marginalia-export-selective-heading">Selected Sessions</h2><p className="muted">Choose Sessions from the current pages and filters.</p></div>
        <div className="marginalia-export-selection-summary"><strong>{selectedSessionIds.size} {selectedSessionIds.size === 1 ? "Session" : "Sessions"} selected</strong>{selectedSessionIds.size ? <span>{selectedBookCount} {selectedBookCount === 1 ? "Book" : "Books"}</span> : null}</div>
      </header>

      <section className="marginalia-controls" aria-label="Export Session filters">
        <form role="search" onSubmit={submit}>
          <label htmlFor="marginalia-export-search">Search</label>
          <input id="marginalia-export-search" type="search" value={search} placeholder="Session, notes, or available Book..." onChange={(event) => onSearchChange(event.target.value)} />
          <Button type="submit">Search</Button>
        </form>
        <label className="marginalia-status-filter" htmlFor="marginalia-export-status">Status
          <select id="marginalia-export-status" value={status} onChange={(event) => onStatusChange(event.target.value as MarginaliaStatusFilter)}>
            <option value="all">All</option><option value="active">Active</option><option value="historical">Historical</option>
          </select>
        </label>
      </section>

      {page ? <div className="marginalia-export-page-actions"><Button type="button" size="small" tone="secondary" disabled={!page.items.length || selectedState.pending} onClick={onSelectPage}>Select this page</Button><Button type="button" size="small" tone="secondary" disabled={!selectedSessionIds.size || selectedState.pending} onClick={onClearSelection}>Clear selection</Button></div> : null}

      {!page && loading ? <div className="marginalia-state" aria-live="polite" aria-busy="true">Loading reading sessions...</div> : null}
      {!page && loadError ? <div className="marginalia-state"><ErrorPanel>{loadError.message}</ErrorPanel><Button type="button" tone="secondary" onClick={onRetry}>Retry</Button></div> : null}
      {page ? <div className={loading ? "marginalia-results marginalia-results--loading" : "marginalia-results"} aria-busy={loading}>
        {loadError ? <div className="marginalia-inline-error"><ErrorPanel>{loadError.message}</ErrorPanel><Button type="button" tone="secondary" onClick={onRetry}>Retry</Button></div> : null}
        <PaginatedListFrameComponent page={pageNumber} pageSize={pageSize} count={page.count} hasPrevious={Boolean(page.previous)} hasNext={Boolean(page.next)} itemLabel="Export Sessions" onPageChange={onPageChange} onPageSizeChange={onPageSizeChange}>
          {page.items.length ? <div className="marginalia-export-session-rows">{page.items.map((session) => <MarginaliaExportSessionRow key={session.id} session={session} selected={selectedSessionIds.has(session.id)} disabled={selectedState.pending} onChange={(selected) => onSessionSelectionChange(session, selected)} />)}</div> : <div className="marginalia-empty"><p>No reading sessions found.</p></div>}
        </PaginatedListFrameComponent>
      </div> : null}

      <div className="marginalia-export-submit">
        <ActionFeedbackComponent state={selectedState} />
        <Button type="button" disabled={!selectedSessionIds.size || selectedState.pending} onClick={onSelectedExport}>{selectedState.pending ? "Preparing..." : "Export selected Sessions"}</Button>
      </div>
    </section>
  </div>;
}

function MarginaliaExportSessionRow({ session, selected, disabled, onChange }: { session: ReadingSessionSummary; selected: boolean; disabled: boolean; onChange: (selected: boolean) => void }) {
  const sessionName = marginaliaSessionDisplayName(session);
  const bookTitle = session.book.unavailable ? "Book unavailable" : session.book.title || "Untitled Book";
  const relevantDate = session.completedAt ?? session.updatedAt ?? session.startedAt;
  return <article className="marginalia-export-session-row">
    <div className="marginalia-export-session-row__selection"><input type="checkbox" aria-label={`Select ${sessionName}`} checked={selected} disabled={disabled} onChange={(event) => onChange(event.target.checked)} /></div>
    <div className="marginalia-export-session-row__cover"><BookCoverComponent coverUrl={session.book.coverUrl} title={bookTitle} /></div>
    <div className="marginalia-export-session-row__body">
      <div className="marginalia-export-session-row__heading"><strong>{sessionName}</strong><Badge tone={session.isActive ? "success" : "default"}>{session.isActive ? "Active" : "Historical"}</Badge></div>
      <p className={session.book.unavailable ? "muted" : ""}>{bookTitle}</p>
      <div className="marginalia-session-row__facts"><span>{formatCount(session.annotationCount, "annotation")}</span>{session.progression !== null ? <><span className="css-dot" aria-hidden="true" /><span>{formatProgression(session.progression)} read</span></> : null}<span className="css-dot" aria-hidden="true" /><time dateTime={relevantDate}>{formatDate(relevantDate)}</time></div>
    </div>
  </article>;
}

function formatDate(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "Unknown date" : new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(parsed);
}

function formatProgression(value: number): string {
  return `${Math.round(Math.min(1, Math.max(0, value)) * 100)}%`;
}

function formatCount(count: number, singular: string): string {
  return `${count} ${singular}${count === 1 ? "" : "s"}`;
}
