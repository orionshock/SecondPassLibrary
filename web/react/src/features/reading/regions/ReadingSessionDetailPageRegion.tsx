import type { Page, ReadingAnnotation, ReadingProgress, ReadingSessionDetail } from "@second-pass/spl-api";
import { Link } from "react-router-dom";

import { Badge, Button, ErrorPanel, Surface } from "../../../components/ui";
import { BookCoverComponent } from "../../../shared/books/BookCoverComponent";
import { OrderMenuComponent, type OrderMenuOption } from "../../../shared/forms/OrderMenuComponent";
import { PaginatedListFrameComponent } from "../../../shared/pagination/PaginatedListFrameComponent";
import type { ReadingAnnotationFilter, ReadingAnnotationOrder } from "../readingSessionDetailQuery";

const annotationOrders: readonly OrderMenuOption<ReadingAnnotationOrder>[] = [
  { value: "newest", label: "Newest", icon: "south" },
  { value: "oldest", label: "Oldest", icon: "north" },
];

export interface ReadingProgressLoadState {
  progress?: ReadingProgress;
  loading: boolean;
  error?: Error;
}

export interface ReadingAnnotationsLoadState {
  page?: Page<ReadingAnnotation>;
  loading: boolean;
  error?: Error;
}

export function ReadingSessionDetailPageRegion({ session, progress, annotations, annotationFilter, annotationOrder, pageNumber, pageSize, onAnnotationFilterChange, onAnnotationOrderChange, onPageChange, onPageSizeChange, onRetryProgress, onRetryAnnotations }: {
  session: ReadingSessionDetail;
  progress: ReadingProgressLoadState;
  annotations: ReadingAnnotationsLoadState;
  annotationFilter: ReadingAnnotationFilter;
  annotationOrder: ReadingAnnotationOrder;
  pageNumber: number;
  pageSize: number;
  onAnnotationFilterChange: (filter: ReadingAnnotationFilter) => void;
  onAnnotationOrderChange: (order: ReadingAnnotationOrder) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetryProgress: () => void;
  onRetryAnnotations: () => void;
}) {
  return <div className="reading-session-detail">
    <div className="reading-session-detail__summary-grid">
      <SessionSummaryRegion session={session} />
      <BookContextRegion session={session} />
      <ProgressRegion state={progress} onRetry={onRetryProgress} />
    </div>
    <AnnotationsRegion state={annotations} filter={annotationFilter} order={annotationOrder} pageNumber={pageNumber} pageSize={pageSize} onFilterChange={onAnnotationFilterChange} onOrderChange={onAnnotationOrderChange} onPageChange={onPageChange} onPageSizeChange={onPageSizeChange} onRetry={onRetryAnnotations} />
  </div>;
}

function SessionSummaryRegion({ session }: { session: ReadingSessionDetail }) {
  return <Surface title="Session">
    <div className="reading-session-detail__heading-facts">
      <Badge tone={session.isActive ? "success" : "default"}>{session.isActive ? "Active" : "Historical"}</Badge>
      <span>{formatCount(session.annotationCount, "annotation")}</span>
    </div>
    <dl className="reading-session-detail__facts">
      <div><dt>Started</dt><dd><time dateTime={session.startedAt}>{formatDate(session.startedAt)}</time></dd></div>
      <div><dt>Updated</dt><dd><time dateTime={session.updatedAt}>{formatDate(session.updatedAt)}</time></dd></div>
      {session.completedAt ? <div><dt>Completed</dt><dd><time dateTime={session.completedAt}>{formatDate(session.completedAt)}</time></dd></div> : null}
    </dl>
    {session.notes.trim() ? <p className="reading-session-detail__notes">{session.notes}</p> : null}
  </Surface>;
}

function BookContextRegion({ session }: { session: ReadingSessionDetail }) {
  if (session.book.unavailable || !session.book.id) {
    return <Surface title="Book"><div className="reading-session-detail__unavailable"><BookCoverComponent coverUrl={null} title="Book unavailable" /><p>This reading history is still yours, but the related Book is not currently available.</p></div></Surface>;
  }
  return <Surface title="Book">
    <div className="reading-session-detail__book">
      <BookCoverComponent coverUrl={session.book.coverUrl} title={session.book.title || "Untitled Book"} />
      <div>
        <strong>{session.book.title || "Untitled Book"}</strong>
        {session.book.authors.length ? <p>{session.book.authors.map((author) => author.name).join(", ")}</p> : null}
        {session.book.series ? <p>{session.book.series.name}{session.book.seriesIndex ? ` ${session.book.seriesIndex}` : ""}</p> : null}
        {session.canOpen ? <Link className="button button--small button--secondary" to={`/library/books/${encodeURIComponent(session.book.id)}`}>View Book</Link> : null}
      </div>
    </div>
  </Surface>;
}

function ProgressRegion({ state, onRetry }: { state: ReadingProgressLoadState; onRetry: () => void }) {
  return <Surface title="Progress">
    {state.loading && !state.progress ? <p aria-live="polite" aria-busy="true">Loading progress...</p> : null}
    {state.error ? <div><ErrorPanel>{state.error.message}</ErrorPanel><Button type="button" size="small" tone="secondary" onClick={onRetry}>Retry</Button></div> : null}
    {state.progress ? <div className="reading-session-detail__progress">
      <strong>{state.progress.progression === null ? "No recorded percentage" : `${formatProgression(state.progress.progression)} read`}</strong>
      {state.progress.updatedAt ? <span>Updated <time dateTime={state.progress.updatedAt}>{formatDate(state.progress.updatedAt)}</time></span> : null}
    </div> : null}
  </Surface>;
}

function AnnotationsRegion({ state, filter, order, pageNumber, pageSize, onFilterChange, onOrderChange, onPageChange, onPageSizeChange, onRetry }: {
  state: ReadingAnnotationsLoadState;
  filter: ReadingAnnotationFilter;
  order: ReadingAnnotationOrder;
  pageNumber: number;
  pageSize: number;
  onFilterChange: (filter: ReadingAnnotationFilter) => void;
  onOrderChange: (order: ReadingAnnotationOrder) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
}) {
  return <section className="reading-session-detail__annotations" aria-labelledby="reading-session-annotations-heading">
    <header><h2 id="reading-session-annotations-heading">Marginalia</h2><div className="reading-session-detail__annotation-controls">
      <label htmlFor="reading-annotation-kind">Show <select id="reading-annotation-kind" value={filter} onChange={(event) => onFilterChange(event.target.value as ReadingAnnotationFilter)}><option value="all">All</option><option value="highlight">Highlights</option><option value="bookmark">Bookmarks</option></select></label>
      <OrderMenuComponent label="Order" value={order} options={annotationOrders} onChange={onOrderChange} size="small" />
    </div></header>
    {!state.page && state.loading ? <p aria-live="polite" aria-busy="true">Loading marginalia...</p> : null}
    {!state.page && state.error ? <div><ErrorPanel>{state.error.message}</ErrorPanel><Button type="button" size="small" tone="secondary" onClick={onRetry}>Retry</Button></div> : null}
    {state.page ? <div aria-busy={state.loading}>
      {state.error ? <div className="reading-inline-error"><ErrorPanel>{state.error.message}</ErrorPanel><Button type="button" size="small" tone="secondary" onClick={onRetry}>Retry</Button></div> : null}
      <PaginatedListFrameComponent page={pageNumber} pageSize={pageSize} count={state.page.count} hasPrevious={Boolean(state.page.previous)} hasNext={Boolean(state.page.next)} itemLabel="Marginalia" onPageChange={onPageChange} onPageSizeChange={onPageSizeChange}>
        {state.page.items.length ? <div className="reading-annotation-rows">{state.page.items.map((annotation) => <AnnotationRowComponent key={annotation.id} annotation={annotation} />)}</div> : <p className="reading-empty">No marginalia found.</p>}
      </PaginatedListFrameComponent>
    </div> : null}
  </section>;
}

function AnnotationRowComponent({ annotation }: { annotation: ReadingAnnotation }) {
  return <article className="reading-annotation-row">
    <header><Badge>{annotation.kind === "highlight" ? "Highlight" : "Bookmark"}</Badge><time dateTime={annotation.createdAt}>{formatDate(annotation.createdAt)}</time></header>
    {annotation.kind === "highlight" && annotation.highlightText.trim() ? <blockquote>{annotation.highlightText}</blockquote> : null}
    {annotation.commentText.trim() ? <p className="reading-annotation-row__comment">{annotation.commentText}</p> : null}
    {annotation.kind === "bookmark" && !annotation.commentText.trim() ? <p className="muted">Saved location</p> : null}
  </article>;
}

function formatDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Unknown date";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(parsed);
}

function formatProgression(value: number): string {
  return `${Math.round(Math.min(1, Math.max(0, value)) * 100)}%`;
}

function formatCount(count: number, singular: string): string {
  return `${count} ${singular}${count === 1 ? "" : "s"}`;
}
