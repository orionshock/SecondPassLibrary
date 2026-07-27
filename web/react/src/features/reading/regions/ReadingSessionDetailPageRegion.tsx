import type { Page, ReadingAnnotation, ReadingProgress, ReadingSessionDetail } from "@second-pass/spl-api";
import { Link } from "react-router-dom";

import { Badge, Button, ErrorPanel, Surface } from "../../../components/ui";
import { MaterialIcon } from "../../../components/icons/MaterialIcon";
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
    <SessionSummaryRegion session={session} progress={progress} onRetryProgress={onRetryProgress} />
    <AnnotationsRegion state={annotations} filter={annotationFilter} order={annotationOrder} pageNumber={pageNumber} pageSize={pageSize} onFilterChange={onAnnotationFilterChange} onOrderChange={onAnnotationOrderChange} onPageChange={onPageChange} onPageSizeChange={onPageSizeChange} onRetry={onRetryAnnotations} />
  </div>;
}

function SessionSummaryRegion({ session, progress, onRetryProgress }: { session: ReadingSessionDetail; progress: ReadingProgressLoadState; onRetryProgress: () => void }) {
  const bookAvailable = !session.book.unavailable && Boolean(session.book.id);
  const sessionName = session.name.trim() || "Unnamed session";
  return <Surface>
    <div className="reading-session-summary">
      <div className="reading-session-summary__cover"><BookCoverComponent coverUrl={bookAvailable ? session.book.coverUrl : null} title={bookAvailable ? session.book.title || "Untitled Book" : "Book unavailable"} /></div>
      <div className="reading-session-summary__main">
        <header className="reading-session-summary__book-header">
          <div>
            <p className="eyebrow">{bookAvailable ? "Book" : "Book unavailable"}</p>
            {bookAvailable ? <>
              <h2>{session.book.title || "Untitled Book"}</h2>
              {session.book.authors.length ? <p className="reading-session-summary__book-meta">{session.book.authors.map((author) => author.name).join(", ")}</p> : null}
              {session.book.series ? <p className="reading-session-summary__book-meta">{session.book.series.name}{session.book.seriesIndex ? ` ${session.book.seriesIndex}` : ""}</p> : null}
            </> : <p className="reading-session-summary__unavailable">This reading history is still yours, but the related Book is not currently available.</p>}
          </div>
          {bookAvailable && session.canOpen && session.book.id ? <Link className="button button--small button--secondary" to={`/library/books/${encodeURIComponent(session.book.id)}`}>View Book</Link> : null}
        </header>
        <div className="reading-session-summary__session">
          <div className="reading-session-summary__session-heading"><h3>{sessionName}</h3><Badge tone={session.isActive ? "success" : "default"}>{session.isActive ? "Active" : "Historical"}</Badge></div>
          <div className="reading-session-summary__stats">
            <span>{formatCount(session.annotationCount, "annotation")}</span>
            {progress.loading && !progress.progress ? <span aria-live="polite" aria-busy="true">Loading progress...</span> : null}
            {progress.progress ? <span aria-label={progress.progress.progression === null ? "Progress unavailable" : "Reading progress"}>{progress.progress.progression === null ? "No recorded percentage" : `${formatProgression(progress.progress.progression)} read`}</span> : null}
          </div>
          <dl className="reading-session-detail__facts">
            <div><dt>Started</dt><dd><time dateTime={session.startedAt}>{formatDate(session.startedAt)}</time></dd></div>
            <div><dt>Updated</dt><dd><time dateTime={session.updatedAt}>{formatDate(session.updatedAt)}</time></dd></div>
            {session.completedAt ? <div><dt>Completed</dt><dd><time dateTime={session.completedAt}>{formatDate(session.completedAt)}</time></dd></div> : null}
          </dl>
          {progress.error ? <div className="reading-session-summary__progress-error"><ErrorPanel>{progress.error.message}</ErrorPanel><Button type="button" size="small" tone="secondary" onClick={onRetryProgress}>Retry</Button></div> : null}
        </div>
      </div>
      {session.notes.trim() ? <div className="reading-session-detail__notes"><span className="eyebrow">Session note</span><p>{session.notes}</p></div> : null}
    </div>
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
  const highlightColor = safeHighlightColor(annotation.highlightColor);
  return <article className="reading-annotation-row">
    <div className="reading-annotation-row__marker"><MaterialIcon name={annotation.kind === "bookmark" ? "bookmark" : annotation.hasComment ? "chat_bubble" : "border_color"} /></div>
    <div className="reading-annotation-row__content">
      {annotation.kind === "bookmark" ? <strong>Bookmark</strong> : null}
      {annotation.kind === "highlight" && annotation.highlightText.trim() ? <blockquote className={`reading-annotation-row__quote reading-annotation-row__quote--${highlightColor}`}>{annotation.highlightText}</blockquote> : null}
      {annotation.commentText.trim() ? <p className="reading-annotation-row__comment">{annotation.commentText}</p> : null}
      {annotation.kind === "bookmark" && !annotation.commentText.trim() ? <p className="muted">Saved location</p> : null}
      <time dateTime={annotation.createdAt}>{formatDate(annotation.createdAt)}</time>
    </div>
  </article>;
}

function safeHighlightColor(value: string): "yellow" | "green" | "blue" | "pink" | "purple" | "orange" {
  const normalized = value.trim().toLowerCase();
  return normalized === "green" || normalized === "blue" || normalized === "pink" || normalized === "purple" || normalized === "orange" ? normalized : "yellow";
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
