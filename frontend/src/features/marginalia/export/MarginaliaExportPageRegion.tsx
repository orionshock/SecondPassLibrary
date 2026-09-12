import type { MarginaliaBookSummary, MarginaliaExportCandidate, Page } from "@second-pass/spl-api";
import { useEffect, useRef, type FormEvent } from "react";

import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import { Badge, Button, ErrorPanel, Surface } from "../../../components/UiPrimitives";
import { BookCover } from "../../../shared/books/BookCover";
import { ActionFeedback } from "../../../shared/feedback/ActionFeedback";
import type { MutationState } from "../../../shared/feedback/mutationState";
import { marginaliaSessionDisplayName } from "../../../shared/marginaliaSessionDisplayName";
import { PaginatedListFrame } from "../../../shared/pagination/PaginatedListFrame";
import { marginaliaSessionNoteExcerpt } from "../browse/marginaliaSessionNoteExcerpt";
import { isNestedInteractiveClick } from "../components/selectionClick";
import type { MarginaliaExportStatusFilter, MarginaliaExportView } from "./marginaliaExportQuery";

export interface MarginaliaExportLimitFailure { message: string; guidance: string; limitLabel: string; }

interface ExportPageProps {
  page?: Page<MarginaliaExportCandidate>; pageNumber: number; pageSize: number; search: string;
  status: MarginaliaExportStatusFilter; view: MarginaliaExportView; loading: boolean; loadError?: Error;
  completeState: MutationState; completeLimitFailure?: MarginaliaExportLimitFailure;
  selectedState: MutationState; selectedLimitFailure?: MarginaliaExportLimitFailure;
  selectedSessionIds: ReadonlySet<string>; selectedBookCount: number; includeEmptySessions: boolean;
  onIncludeEmptySessionsChange: (include: boolean) => void; onSearchChange: (value: string) => void;
  onSearch: () => void; onStatusChange: (value: MarginaliaExportStatusFilter) => void;
  onViewChange: (view: MarginaliaExportView) => void; onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void; onRetry: () => void; onCompleteExport: () => void;
  onSessionSelectionChange: (session: MarginaliaExportCandidate, selected: boolean) => void;
  onSelectPage: () => void; onClearSelection: () => void; onSelectedExport: () => void;
}

export function MarginaliaExportPageRegion(props: ExportPageProps) {
  const { page, pageNumber, pageSize, search, status, view, loading, loadError, completeState, completeLimitFailure, selectedState, selectedLimitFailure, selectedSessionIds, selectedBookCount, includeEmptySessions, onIncludeEmptySessionsChange, onSearchChange, onSearch, onStatusChange, onViewChange, onPageChange, onPageSizeChange, onRetry, onCompleteExport, onSessionSelectionChange, onSelectPage, onClearSelection, onSelectedExport } = props;
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); onSearch(); }

  return <div className="marginalia-export-page">
    <label className="marginalia-empty-sessions-toggle marginalia-export-empty-sessions"><input type="checkbox" checked={includeEmptySessions} disabled={completeState.pending || selectedState.pending} onChange={(event) => onIncludeEmptySessionsChange(event.target.checked)} />Include empty Reading Sessions</label>
    <Surface title="Complete archive"><div className="marginalia-export-complete">
      <p>Includes Reading Sessions for Books that are no longer available.</p>
      <div className="marginalia-export-action-row"><MarginaliaExportFeedback state={completeState} limitFailure={completeLimitFailure} /><Button type="button" aria-label={completeState.pending ? "Preparing complete archive" : undefined} disabled={completeState.pending} onClick={onCompleteExport}>{completeState.pending ? "Preparing…" : "Download complete archive"}</Button></div>
    </div></Surface>

    <section className="marginalia-export-selective" aria-labelledby="marginalia-export-selective-heading">
      <header className="marginalia-export-selective__header">
        <div><h2 id="marginalia-export-selective-heading">Selected Reading Sessions</h2><p className="muted">Selections remain checked as you change pages, views, or filters.</p></div>
        <div className="marginalia-export-selection-summary"><strong>{selectedSessionIds.size} {selectedSessionIds.size === 1 ? "Reading Session" : "Reading Sessions"} selected</strong>{selectedSessionIds.size ? <span>{selectedBookCount} {selectedBookCount === 1 ? "Book" : "Books"}</span> : null}</div>
      </header>
      <div className="marginalia-view-selector" role="group" aria-label="Export views">
        <button type="button" className={view === "sessions" ? "active" : ""} aria-label="By Reading Session" aria-pressed={view === "sessions"} onClick={() => onViewChange("sessions")}><MaterialIcon name="history" /><span>By Reading Session</span></button>
        <button type="button" className={view === "books" ? "active" : ""} aria-label="By Book" aria-pressed={view === "books"} onClick={() => onViewChange("books")}><MaterialIcon name="menu_book" /><span>By Book</span></button>
      </div>
      <section className="marginalia-controls" aria-label="Reading Session export filters">
        <form role="search" onSubmit={submit}><label htmlFor="marginalia-export-search">Search</label><input id="marginalia-export-search" type="search" value={search} placeholder={view === "books" ? "Title, author, or series…" : "Reading Session, note, or Book…"} onChange={(event) => onSearchChange(event.target.value)} /><Button type="submit">Search</Button></form>
        <label className="marginalia-status-filter" htmlFor="marginalia-export-status">Status<select id="marginalia-export-status" value={status} onChange={(event) => onStatusChange(event.target.value as MarginaliaExportStatusFilter)}><option value="all">All</option><option value="active">Active</option><option value="closed">Closed</option></select></label>
      </section>
      {page ? <div className="marginalia-export-page-actions"><Button type="button" size="small" tone="secondary" disabled={!page.items.length || selectedState.pending} onClick={onSelectPage}>Select this page</Button><Button type="button" size="small" tone="secondary" disabled={!selectedSessionIds.size || selectedState.pending} onClick={onClearSelection}>Clear selection</Button></div> : null}
      {!page && loading ? <div className="marginalia-state" aria-live="polite" aria-busy="true">Loading Reading Sessions…</div> : null}
      {!page && loadError ? <div className="marginalia-state"><ErrorPanel>{loadError.message}</ErrorPanel><Button type="button" tone="secondary" onClick={onRetry}>Retry</Button></div> : null}
      {page ? <div className={loading ? "marginalia-results marginalia-results--loading" : "marginalia-results"} aria-busy={loading}>
        {loadError ? <div className="marginalia-inline-error"><ErrorPanel>{loadError.message}</ErrorPanel><Button type="button" tone="secondary" onClick={onRetry}>Retry</Button></div> : null}
        <PaginatedListFrame page={pageNumber} pageSize={pageSize} count={page.count} hasPrevious={Boolean(page.previous)} hasNext={Boolean(page.next)} itemLabel="Reading Sessions to export" onPageChange={onPageChange} onPageSizeChange={onPageSizeChange}>
          {page.items.length ? view === "books" ? <MarginaliaExportBookGroups sessions={page.items} selectedSessionIds={selectedSessionIds} disabled={selectedState.pending} onChange={onSessionSelectionChange} /> : <div className="marginalia-export-session-rows">{page.items.map((session) => <MarginaliaExportSessionRow key={session.id} session={session} selected={selectedSessionIds.has(session.id)} disabled={selectedState.pending} showCover onChange={(selected) => onSessionSelectionChange(session, selected)} />)}</div> : <div className="marginalia-empty"><p>No Reading Sessions match these filters.</p></div>}
        </PaginatedListFrame>
      </div> : null}
      <div className="marginalia-export-submit"><MarginaliaExportFeedback state={selectedState} limitFailure={selectedLimitFailure} /><Button type="button" disabled={!selectedSessionIds.size || selectedState.pending} onClick={onSelectedExport}>{selectedState.pending ? "Preparing…" : "Export selected"}</Button></div>
    </section>
  </div>;
}

function MarginaliaExportBookGroups({ sessions, selectedSessionIds, disabled, onChange }: { sessions: readonly MarginaliaExportCandidate[]; selectedSessionIds: ReadonlySet<string>; disabled: boolean; onChange: (session: MarginaliaExportCandidate, selected: boolean) => void }) {
  const groups = new Map<string, { book: MarginaliaBookSummary; sessions: MarginaliaExportCandidate[] }>();
  for (const session of sessions) {
    const group = groups.get(session.book.id) ?? { book: session.book, sessions: [] };
    group.sessions.push(session); groups.set(session.book.id, group);
  }
  return <div className="marginalia-export-book-groups">{[...groups.values()].map(({ book, sessions: bookSessions }) => {
    const selectedCount = bookSessions.filter((session) => selectedSessionIds.has(session.id)).length;
    const state = selectedCount === 0 ? "none" : selectedCount === bookSessions.length ? "all" : "some";
    const setGroupSelection = (selected: boolean) => bookSessions.forEach((session) => onChange(session, selected));
    return <section className={`marginalia-export-book-group${disabled ? "" : " marginalia-selection-target"}${state === "all" ? " marginalia-selection-target--selected" : ""}`} key={book.id} onClick={disabled ? undefined : (event) => { if (!isNestedInteractiveClick(event)) setGroupSelection(state !== "all"); }}>
      <div className="marginalia-export-book-group__summary">
        <BookSelectionCheckbox book={book} state={state} disabled={disabled} onChange={setGroupSelection} />
        <div className="marginalia-export-book-group__cover"><BookCover coverUrl={book.coverUrl} title={book.title || "Untitled Book"} /></div>
        <div className="marginalia-export-book-group__identity"><h3>{book.title || "Untitled Book"}</h3>{book.authors.length ? <p>{book.authors.map(({ name }) => name).join(", ")}</p> : null}{book.series ? <p>{book.series.name}{book.series.seriesIndex ? ` ${book.series.seriesIndex}` : ""}</p> : null}<p className="marginalia-book-facts"><span>{formatCount(book.sessionCount, "Reading Session")}</span><span>{book.activeSessionCount} active</span><span>Last activity <time dateTime={book.lastActivityAt}>{formatDate(book.lastActivityAt)}</time></span></p></div>
      </div>
      <div className="marginalia-export-book-group__sessions">{bookSessions.map((session) => <MarginaliaExportSessionRow key={session.id} session={session} selected={selectedSessionIds.has(session.id)} disabled={disabled} showCover={false} onChange={(selected) => onChange(session, selected)} />)}</div>
    </section>;
  })}</div>;
}

function BookSelectionCheckbox({ book, state, disabled, onChange }: { book: MarginaliaBookSummary; state: "none" | "some" | "all"; disabled: boolean; onChange: (selected: boolean) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => { if (inputRef.current) inputRef.current.indeterminate = state === "some"; }, [state]);
  return <input ref={inputRef} type="checkbox" checked={state === "all"} aria-checked={state === "some" ? "mixed" : state === "all"} aria-label={`Select Reading Sessions from ${book.title || "Untitled Book"}`} disabled={disabled} onChange={(event) => onChange(event.target.checked)} />;
}

function MarginaliaExportFeedback({ state, limitFailure }: { state: MutationState; limitFailure?: MarginaliaExportLimitFailure }) {
  if (!limitFailure) return <ActionFeedback state={state} />;
  return <ErrorPanel><p>{limitFailure.message}</p><p>{limitFailure.guidance}</p><p>{limitFailure.limitLabel}</p></ErrorPanel>;
}

function MarginaliaExportSessionRow({ session, selected, disabled, showCover, onChange }: { session: MarginaliaExportCandidate; selected: boolean; disabled: boolean; showCover: boolean; onChange: (selected: boolean) => void }) {
  const sessionName = marginaliaSessionDisplayName(session); const bookTitle = session.book.title || "Untitled Book";
  const relevantDate = session.closedAt ?? session.updatedAt; const noteExcerpt = marginaliaSessionNoteExcerpt(session.notes);
  return <article className={`marginalia-export-session-row${showCover ? "" : " marginalia-export-session-row--no-cover"}${disabled ? "" : " marginalia-selection-target marginalia-selection-target--child"}${selected ? " marginalia-selection-target--selected" : ""}`} onClick={disabled ? (event) => event.stopPropagation() : (event) => { event.stopPropagation(); if (!isNestedInteractiveClick(event)) onChange(!selected); }}>
    <div className="marginalia-export-session-row__selection"><input type="checkbox" aria-label={`Select ${sessionName} for ${bookTitle}`} checked={selected} disabled={disabled} onChange={(event) => onChange(event.target.checked)} /></div>
    {showCover ? <div className="marginalia-export-session-row__cover"><BookCover coverUrl={session.book.coverUrl} title={bookTitle} /></div> : null}
    <div className="marginalia-export-session-row__body"><div className="marginalia-export-session-row__heading"><strong>{sessionName}</strong><Badge tone={session.status === "active" ? "success" : "default"}>{session.status === "active" ? "Active" : "Closed"}</Badge></div><p>{bookTitle}</p><div className="marginalia-session-row__facts"><span>{formatCount(session.annotationCount, "annotation")}</span><span className="css-dot" aria-hidden="true" /><time dateTime={relevantDate}>{formatDate(relevantDate)}</time></div>{noteExcerpt ? <blockquote className="marginalia-session-row__note">{noteExcerpt}</blockquote> : null}</div>
  </article>;
}

function formatDate(value: string): string { const parsed = new Date(value); return Number.isNaN(parsed.getTime()) ? "Unknown date" : new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(parsed); }
function formatCount(count: number, singular: string): string { return `${count} ${singular}${count === 1 ? "" : "s"}`; }
