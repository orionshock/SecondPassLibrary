import type { MarginaliaAnnotation, MarginaliaSessionEnvelope } from "@second-pass/spl-api";
import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type MouseEvent, type ReactNode } from "react";
import { Link } from "react-router";

import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import { Badge, Button, ErrorPanel, Surface } from "../../../components/UiPrimitives";
import type { MutationState } from "../../../shared/feedback/mutationState";
import { BookCover } from "../../../shared/books/BookCover";
import { OrderMenu, type OrderMenuOption } from "../../../shared/forms/OrderMenu";

export type MarginaliaAnnotationOrdering = "reading" | "newest" | "oldest";

export const marginaliaAnnotationOrderingOptions: readonly OrderMenuOption<MarginaliaAnnotationOrdering>[] = [
  { value: "reading", label: "Reading order", icon: "format_list_numbered" },
  { value: "newest", label: "Newest first", icon: "arrow_downward" },
  { value: "oldest", label: "Oldest first", icon: "arrow_upward" },
];

export function orderMarginaliaAnnotations(
  annotations: readonly MarginaliaAnnotation[],
  ordering: MarginaliaAnnotationOrdering,
): MarginaliaAnnotation[] {
  if (ordering === "reading") return [...annotations];
  return annotations
    .map((annotation, readingPosition) => ({ annotation, readingPosition }))
    .sort((left, right) => {
      const leftTimestamp = Date.parse(left.annotation.createdAt);
      const rightTimestamp = Date.parse(right.annotation.createdAt);
      const timestampDifference = ordering === "newest"
        ? rightTimestamp - leftTimestamp
        : leftTimestamp - rightTimestamp;
      return timestampDifference || left.readingPosition - right.readingPosition;
    })
    .map(({ annotation }) => annotation);
}

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
  deleteState,
  exportState,
  onClose,
  onDelete,
  onExport,
  onRetryAnnotations,
}: {
  detail: MarginaliaSessionEnvelope;
  annotations: MarginaliaAnnotationsLoadState;
  sessionNote: ReactNode;
  closeState: MutationState;
  deleteState: MutationState;
  exportState: MutationState;
  onClose: () => void;
  onDelete: () => void;
  onExport: () => void;
  onRetryAnnotations: () => void;
}) {
  return <div className="marginalia-session-detail">
    <SessionSummaryRegion detail={detail} sessionNote={sessionNote} closeState={closeState} deleteState={deleteState} exportState={exportState} onClose={onClose} onDelete={onDelete} onExport={onExport} />
    <AnnotationsRegion state={annotations} onRetry={onRetryAnnotations} />
  </div>;
}

function SessionSummaryRegion({ detail, sessionNote, closeState, deleteState, exportState, onClose, onDelete, onExport }: {
  detail: MarginaliaSessionEnvelope;
  sessionNote: ReactNode;
  closeState: MutationState;
  deleteState: MutationState;
  exportState: MutationState;
  onClose: () => void;
  onDelete: () => void;
  onExport: () => void;
}) {
  const [deleteConfirmationOpen, setDeleteConfirmationOpen] = useState(false);
  const deleteButton = useRef<HTMLButtonElement>(null);
  const { book, session } = detail;
  const lifecyclePending = closeState.pending || deleteState.pending;
  const progressLabel = session.progress
    ? session.progress.locationLabel.trim() ? session.progress.locationLabel : "Saved location"
    : "No saved progress";

  function cancelDeleteConfirmation() {
    if (deleteState.pending) return;
    setDeleteConfirmationOpen(false);
    deleteButton.current?.focus();
  }

  function continueDelete() {
    if (lifecyclePending || exportState.pending) return;
    setDeleteConfirmationOpen(false);
    const confirmed = confirmPermanentSessionDeletion(onDelete);
    if (!confirmed) {
      deleteButton.current?.focus();
    }
  }

  return <Surface>
    <div className="marginalia-session-summary">
      <div className="marginalia-session-summary__cover"><BookCover coverUrl={book.coverUrl} title={book.title || "Untitled Book"} /></div>
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
            {session.status === "active" ? <Button type="button" size="small" tone="secondary" className="marginalia-session-summary__lifecycle-action" disabled={lifecyclePending} onClick={onClose}><MaterialIcon name="close" />{closeState.pending ? "Closing..." : "Close Session"}</Button> : null}
            <Button ref={deleteButton} type="button" size="small" tone="danger" className="marginalia-session-summary__lifecycle-action" disabled={lifecyclePending} onClick={() => setDeleteConfirmationOpen(true)}><MaterialIcon name="delete" />{deleteState.pending ? "Deleting…" : "Delete"}</Button>
            {closeState.error ? <span className="field-error" role="alert">{closeState.error.message}</span> : null}
            {closeState.message ? <span className="success-message" role="status">{closeState.message}</span> : null}
            {deleteState.error ? <span className="field-error" role="alert">{deleteState.error.message}</span> : null}
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
    {deleteConfirmationOpen ? <MarginaliaSessionDeleteDialog
      sessionName={session.name}
      bookTitle={book.title || "Untitled Book"}
      pending={lifecyclePending}
      exportState={exportState}
      onCancel={cancelDeleteConfirmation}
      onContinue={continueDelete}
      onExport={onExport}
    /> : null}
  </Surface>;
}

export function MarginaliaSessionDeleteDialog({ sessionName, bookTitle, pending, exportState, onCancel, onContinue, onExport }: {
  sessionName: string;
  bookTitle: string;
  pending: boolean;
  exportState: MutationState;
  onCancel: () => void;
  onContinue: () => void;
  onExport: () => void;
}) {
  const cancelButton = useRef<HTMLButtonElement>(null);

  useEffect(() => { cancelButton.current?.focus(); }, []);

  function handleDialogKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      onCancel();
    }
  }

  function handleBackdropClick(event: MouseEvent<HTMLDivElement>) {
    if (event.target === event.currentTarget) onCancel();
  }

  return <div className="marginalia-session-delete-dialog-backdrop" onClick={handleBackdropClick}>
    <div className="marginalia-session-delete-dialog" role="dialog" aria-modal="true" aria-labelledby="marginalia-session-delete-dialog-title" aria-describedby="marginalia-session-delete-dialog-description" onKeyDown={handleDialogKeyDown}>
      <h2 id="marginalia-session-delete-dialog-title">Delete this reading session?</h2>
      <div id="marginalia-session-delete-dialog-description" className="marginalia-session-delete-dialog__body">
        {sessionName.trim() ? <p>Session: <strong>{sessionName}</strong></p> : null}
        <p>Book: <strong>{bookTitle}</strong></p>
        <p>This permanently deletes this Session and all annotations attached to it.</p>
        <p>This cannot be undone.</p>
        <p className="marginalia-session-delete-dialog__export-note">You may export this Session before deleting it.</p>
        {exportState.error ? <span className="field-error" role="alert">{exportState.error.message}</span> : null}
      </div>
      <div className="marginalia-session-delete-dialog__actions">
        <Button type="button" tone="secondary" className="marginalia-session-delete-dialog__export" disabled={pending || exportState.pending} onClick={onExport}><MaterialIcon name="download" />{exportState.pending ? "Exporting…" : "Export Session"}</Button>
        <Button ref={cancelButton} type="button" tone="secondary" disabled={pending} onClick={onCancel}>Cancel</Button>
        <Button type="button" tone="danger" disabled={pending || exportState.pending} onClick={onContinue}>Continue to delete</Button>
      </div>
    </div>
  </div>;
}

export const permanentSessionDeletionWarning = "Permanently delete this Session and all of its annotations? This cannot be undone.";

export function confirmPermanentSessionDeletion(
  onConfirm: () => void,
  confirm: (message: string) => boolean = window.confirm,
): boolean {
  const confirmed = confirm(permanentSessionDeletionWarning);
  if (confirmed) onConfirm();
  return confirmed;
}

function AnnotationsRegion({ state, onRetry }: { state: MarginaliaAnnotationsLoadState; onRetry: () => void }) {
  const [ordering, setOrdering] = useState<MarginaliaAnnotationOrdering>("reading");
  const orderedItems = useMemo(
    () => state.items ? orderMarginaliaAnnotations(state.items, ordering) : undefined,
    [ordering, state.items],
  );
  return <section className="marginalia-session-detail__annotations" aria-labelledby="marginalia-session-annotations-heading">
    <header>
      <h2 id="marginalia-session-annotations-heading">Marginalia</h2>
      {orderedItems && orderedItems.length > 1 ? <OrderMenu
        label="Order"
        ariaLabel="Order marginalia"
        size="small"
        value={ordering}
        options={marginaliaAnnotationOrderingOptions}
        onChange={setOrdering}
      /> : null}
    </header>
    {!state.items && state.loading ? <p aria-live="polite" aria-busy="true">Loading marginalia...</p> : null}
    {!state.items && state.error ? <div><ErrorPanel>{state.error.message}</ErrorPanel><Button type="button" size="small" tone="secondary" onClick={onRetry}>Retry</Button></div> : null}
    {state.items ? <div aria-busy={state.loading}>
      {state.error ? <div className="marginalia-inline-error"><ErrorPanel>{state.error.message}</ErrorPanel><Button type="button" size="small" tone="secondary" onClick={onRetry}>Retry</Button></div> : null}
      {orderedItems?.length ? <div className="marginalia-annotation-rows">{orderedItems.map((annotation) => <AnnotationRowComponent key={annotation.id} annotation={annotation} />)}</div> : <p className="marginalia-empty">No marginalia found.</p>}
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
