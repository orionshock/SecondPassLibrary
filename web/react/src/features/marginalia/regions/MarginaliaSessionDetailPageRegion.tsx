import type { MarginaliaAnnotation, MarginaliaSessionEnvelope } from "@second-pass/spl-api";
import type { ReactNode } from "react";
import { Link } from "react-router";

import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import { Badge, Button, ErrorPanel, Surface } from "../../../components/ui";
import type { MutationState } from "../../../shared/feedback/mutationState";
import { BookCoverComponent } from "../../../shared/books/BookCoverComponent";

export interface MarginaliaAnnotationsLoadState {
  items?: MarginaliaAnnotation[];
  loading: boolean;
  error?: Error;
}

export function MarginaliaSessionDetailPageRegion({
  detail,
  annotations,
  sessionNote,
  closeState,
  onClose,
  onRetryAnnotations,
}: {
  detail: MarginaliaSessionEnvelope;
  annotations: MarginaliaAnnotationsLoadState;
  sessionNote: ReactNode;
  closeState: MutationState;
  onClose: () => void;
  onRetryAnnotations: () => void;
}) {
  return <div className="marginalia-session-detail">
    <SessionSummaryRegion detail={detail} sessionNote={sessionNote} closeState={closeState} onClose={onClose} />
    <AnnotationsRegion state={annotations} onRetry={onRetryAnnotations} />
  </div>;
}

function SessionSummaryRegion({ detail, sessionNote, closeState, onClose }: {
  detail: MarginaliaSessionEnvelope;
  sessionNote: ReactNode;
  closeState: MutationState;
  onClose: () => void;
}) {
  const { book, session } = detail;
  const progressLabel = session.progress
    ? session.progress.locationLabel.trim() ? session.progress.locationLabel : "Saved location"
    : "No saved progress";

  return <Surface>
    <div className="marginalia-session-summary">
      <div className="marginalia-session-summary__cover"><BookCoverComponent coverUrl={book.coverUrl} title={book.title || "Untitled Book"} /></div>
      <div className="marginalia-session-summary__main">
        <header className="marginalia-session-summary__book-header">
          <div>
            <p className="eyebrow">Book</p>
            <h2>{book.title || "Untitled Book"}</h2>
            {book.authors.length ? <p className="marginalia-session-summary__book-meta">{book.authors.map((author) => author.name).join(", ")}</p> : null}
            {book.series ? <p className="marginalia-session-summary__book-meta">{book.series.name}{book.series.seriesIndex ? ` ${book.series.seriesIndex}` : ""}</p> : null}
          </div>
          {book.canOpen ? <Link className="button button--small button--secondary" to={`/library/books/${encodeURIComponent(book.id)}`}>View Book</Link> : null}
        </header>
        <div className="marginalia-session-summary__session">
          <div className="marginalia-session-summary__status-actions">
            <Badge tone={session.status === "active" ? "success" : "default"}>{session.status === "active" ? "Active" : "Closed"}</Badge>
            {session.status === "active" ? <Button type="button" size="small" tone="danger" disabled={closeState.pending} onClick={onClose}>{closeState.pending ? "Closing..." : "Close Session"}</Button> : null}
            {closeState.error ? <span className="field-error" role="alert">{closeState.error.message}</span> : null}
            {closeState.message ? <span className="success-message" role="status">{closeState.message}</span> : null}
          </div>
          <div className="marginalia-session-summary__stats">
            <span>{formatCount(session.annotationCount, "annotation")}</span>
            <span aria-label="Saved progress">{progressLabel}</span>
          </div>
          <dl className="marginalia-session-detail__facts">
            <div><dt>Started</dt><dd><time dateTime={session.startedAt}>{formatDate(session.startedAt)}</time></dd></div>
            <div><dt>Updated</dt><dd><time dateTime={session.updatedAt}>{formatDate(session.updatedAt)}</time></dd></div>
            {session.closedAt ? <div><dt>Closed</dt><dd><time dateTime={session.closedAt}>{formatDate(session.closedAt)}</time></dd></div> : null}
          </dl>
        </div>
      </div>
      {sessionNote}
    </div>
  </Surface>;
}

function AnnotationsRegion({ state, onRetry }: { state: MarginaliaAnnotationsLoadState; onRetry: () => void }) {
  return <section className="marginalia-session-detail__annotations" aria-labelledby="marginalia-session-annotations-heading">
    <header><h2 id="marginalia-session-annotations-heading">Marginalia</h2></header>
    {!state.items && state.loading ? <p aria-live="polite" aria-busy="true">Loading marginalia...</p> : null}
    {!state.items && state.error ? <div><ErrorPanel>{state.error.message}</ErrorPanel><Button type="button" size="small" tone="secondary" onClick={onRetry}>Retry</Button></div> : null}
    {state.items ? <div aria-busy={state.loading}>
      {state.error ? <div className="marginalia-inline-error"><ErrorPanel>{state.error.message}</ErrorPanel><Button type="button" size="small" tone="secondary" onClick={onRetry}>Retry</Button></div> : null}
      {state.items.length ? <div className="marginalia-annotation-rows">{state.items.map((annotation) => <AnnotationRowComponent key={annotation.id} annotation={annotation} />)}</div> : <p className="marginalia-empty">No marginalia found.</p>}
    </div> : null}
  </section>;
}

function AnnotationRowComponent({ annotation }: { annotation: MarginaliaAnnotation }) {
  const locationLabel = annotation.location.locationLabel.trim() ? annotation.location.locationLabel : null;
  return <article className="marginalia-annotation-row">
    <div className="marginalia-annotation-row__marker"><MaterialIcon name={annotation.kind === "bookmark" ? "bookmark" : annotation.body.note.trim() ? "chat_bubble" : "border_color"} /></div>
    <div className="marginalia-annotation-row__content">
      {locationLabel ? <p className="marginalia-annotation-row__location">{locationLabel}</p> : null}
      {annotation.kind === "bookmark"
        ? !locationLabel ? <strong>Saved location</strong> : null
        : <>
          <blockquote className={`marginalia-annotation-row__quote marginalia-annotation-row__quote--${annotation.body.color}`}>
            {annotation.body.prefix ? <span className="marginalia-annotation-row__quote-context">{annotation.body.prefix}</span> : null}
            <strong className="marginalia-annotation-row__quote-text">{annotation.body.text}</strong>
            {annotation.body.suffix ? <span className="marginalia-annotation-row__quote-context">{annotation.body.suffix}</span> : null}
          </blockquote>
          {annotation.body.note.trim() ? <p className="marginalia-annotation-row__comment">{annotation.body.note}</p> : null}
        </>}
      <time dateTime={annotation.createdAt}>{formatDate(annotation.createdAt)}</time>
    </div>
  </article>;
}

function formatDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Unknown date";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(parsed);
}

function formatCount(count: number, singular: string): string {
  return `${count} ${singular}${count === 1 ? "" : "s"}`;
}
