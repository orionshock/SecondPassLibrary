import type { Page, ReadingAnnotation, ReadingAnnotationCategory, ReadingProgress, ReadingSessionDetail } from "@second-pass/spl-api";
import { useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { Badge, Button, ErrorPanel, Surface } from "../../../components/ui";
import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import { BookCoverComponent } from "../../../shared/books/BookCoverComponent";
import { OrderMenuComponent, type OrderMenuOption } from "../../../shared/forms/OrderMenuComponent";
import { PaginatedListFrameComponent } from "../../../shared/pagination/PaginatedListFrameComponent";
import { allReadingAnnotationCategories, defaultReadingAnnotationCategories, type ReadingAnnotationOrder } from "../readingSessionDetailQuery";

export const annotationOrderOptions: readonly OrderMenuOption<ReadingAnnotationOrder>[] = [
  { value: "newest", label: "Newest created", icon: "south" },
  { value: "oldest", label: "Oldest created", icon: "north" },
  { value: "recently-edited", label: "Recently edited", icon: "edit_calendar" },
  { value: "oldest-edited", label: "Oldest edited", icon: "history" },
];

const annotationCategoryOptions: readonly { value: ReadingAnnotationCategory; label: string; icon: string }[] = [
  { value: "bookmark", label: "Bookmarks", icon: "bookmark" },
  { value: "highlight", label: "Highlights", icon: "border_color" },
  { value: "highlightWithNote", label: "Highlights with notes", icon: "chat_bubble" },
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

export function ReadingSessionDetailPageRegion({ session, progress, annotations, annotationCategories, annotationOrder, pageNumber, pageSize, onAnnotationCategoriesChange, onAnnotationOrderChange, onPageChange, onPageSizeChange, onRetryProgress, onRetryAnnotations }: {
  session: ReadingSessionDetail;
  progress: ReadingProgressLoadState;
  annotations: ReadingAnnotationsLoadState;
  annotationCategories: readonly ReadingAnnotationCategory[];
  annotationOrder: ReadingAnnotationOrder;
  pageNumber: number;
  pageSize: number;
  onAnnotationCategoriesChange: (categories: ReadingAnnotationCategory[]) => void;
  onAnnotationOrderChange: (order: ReadingAnnotationOrder) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetryProgress: () => void;
  onRetryAnnotations: () => void;
}) {
  return <div className="reading-session-detail">
    <SessionSummaryRegion session={session} progress={progress} onRetryProgress={onRetryProgress} />
    <AnnotationsRegion state={annotations} categories={annotationCategories} order={annotationOrder} pageNumber={pageNumber} pageSize={pageSize} onCategoriesChange={onAnnotationCategoriesChange} onOrderChange={onAnnotationOrderChange} onPageChange={onPageChange} onPageSizeChange={onPageSizeChange} onRetry={onRetryAnnotations} />
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

function AnnotationsRegion({ state, categories, order, pageNumber, pageSize, onCategoriesChange, onOrderChange, onPageChange, onPageSizeChange, onRetry }: {
  state: ReadingAnnotationsLoadState;
  categories: readonly ReadingAnnotationCategory[];
  order: ReadingAnnotationOrder;
  pageNumber: number;
  pageSize: number;
  onCategoriesChange: (categories: ReadingAnnotationCategory[]) => void;
  onOrderChange: (order: ReadingAnnotationOrder) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
}) {
  return <section className="reading-session-detail__annotations" aria-labelledby="reading-session-annotations-heading">
    <header><h2 id="reading-session-annotations-heading">Marginalia</h2><div className="reading-session-detail__annotation-controls">
      <AnnotationCategoryMenuComponent value={categories} onChange={onCategoriesChange} />
      <OrderMenuComponent label="Order" value={order} options={annotationOrderOptions} onChange={onOrderChange} size="small" />
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

export function AnnotationCategoryMenuComponent({ value, onChange }: { value: readonly ReadingAnnotationCategory[]; onChange: (categories: ReadingAnnotationCategory[]) => void }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuId = useId();
  const selectedLabel = value.length === allReadingAnnotationCategories.length
    ? "All"
    : value.length === defaultReadingAnnotationCategories.length && defaultReadingAnnotationCategories.every((category) => value.includes(category))
      ? "Highlights"
    : value.length === 1
      ? annotationCategoryOptions.find((option) => option.value === value[0])?.label ?? "Selected"
      : `${value.length} selected`;

  useEffect(() => {
    if (!open) return;
    function dismissOutside(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("pointerdown", dismissOutside);
    return () => document.removeEventListener("pointerdown", dismissOutside);
  }, [open]);

  return <div className="reading-annotation-category-menu">
    <span>Show</span>
    <div
      className="reading-annotation-category-menu__dropdown"
      ref={rootRef}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOpen(false);
      }}
      onKeyDown={(event) => {
        if (event.key !== "Escape") return;
        event.preventDefault();
        setOpen(false);
        buttonRef.current?.focus();
      }}
    >
      <button
        ref={buttonRef}
        type="button"
        className="reading-annotation-category-menu__button"
        aria-label={`Show marginalia, current: ${selectedLabel}`}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => setOpen((current) => !current)}
      >
        <MaterialIcon name="filter_list" />
        <span>{selectedLabel}</span>
        <MaterialIcon name={open ? "expand_less" : "expand_more"} />
      </button>
      {open ? <AnnotationCategoryMenuOptionsComponent id={menuId} value={value} onChange={onChange} /> : null}
    </div>
  </div>;
}

export function AnnotationCategoryMenuOptionsComponent({ id, value, onChange }: { id?: string; value: readonly ReadingAnnotationCategory[]; onChange: (categories: ReadingAnnotationCategory[]) => void }) {
  return <div id={id} className="reading-annotation-category-menu__options" role="menu" aria-label="Show marginalia">
    {annotationCategoryOptions.map((option) => {
      const selected = value.includes(option.value);
      return <button
        key={option.value}
        type="button"
        role="menuitemcheckbox"
        aria-checked={selected}
        disabled={selected && value.length === 1}
        onClick={() => {
          const selectedValues = selected ? value.filter((category) => category !== option.value) : [...value, option.value];
          onChange(allReadingAnnotationCategories.filter((category) => selectedValues.includes(category)));
        }}
      >
        <MaterialIcon name={option.icon} />
        <span>{option.label}</span>
        {selected ? <MaterialIcon name="check" /> : null}
      </button>;
    })}
  </div>;
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
