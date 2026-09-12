import type { MarginaliaBookReference, MarginaliaSessionSummary } from "@second-pass/spl-api";
import { Link } from "react-router";

import { breadcrumbNavigationState } from "../../../app/navigation/breadcrumbs";
import { BookCover } from "../../../shared/books/BookCover";
import { marginaliaSessionDisplayName } from "../../../shared/marginaliaSessionDisplayName";
import { marginaliaSessionBreadcrumbFallback } from "../marginaliaBreadcrumbs";
import { marginaliaSessionNoteExcerpt } from "./marginaliaSessionNoteExcerpt";

export function SessionSummaryRow({ session, book }: { session: MarginaliaSessionSummary; book: MarginaliaBookReference }) {
  const sessionName = marginaliaSessionDisplayName(session);
  const bookTitle = book.title || "Untitled book";
  const relevantDate = session.closedAt ?? session.updatedAt;
  const noteExcerpt = marginaliaSessionNoteExcerpt(session.notes);

  return <article className="marginalia-session-row">
    <div className="marginalia-session-row__cover">
      <BookCover coverUrl={book.coverUrl} title={bookTitle} />
    </div>
    <div className="marginalia-session-row__body">
      <div className="marginalia-session-row__heading">
        <h2><Link to={`/marginalia/sessions/${encodeURIComponent(session.id)}`} state={breadcrumbNavigationState(marginaliaSessionBreadcrumbFallback(session))}>{sessionName}</Link></h2>
      </div>
      <div className="marginalia-session-row__content">
        <div className="marginalia-session-row__identity">
          <p className="marginalia-session-row__book">{bookTitle}</p>
          <div className="marginalia-session-row__facts">
            <span>{session.closedAt ? "Closed" : "Updated"} <time dateTime={relevantDate}>{formatDate(relevantDate)}</time></span>
            <span className="css-dot" aria-hidden="true" /><span>{formatCount(session.annotationCount, "annotation")}</span>
          </div>
        </div>
        {noteExcerpt ? <blockquote className="marginalia-session-row__note">{noteExcerpt}</blockquote> : null}
      </div>
    </div>
    {book.canOpen ? <Link className="button button--small button--secondary marginalia-session-row__book-link" to={`/library/books/${encodeURIComponent(book.id)}`}>View Book</Link> : null}
  </article>;
}

function formatDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Unknown date";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(parsed);
}

function formatCount(count: number, singular: string): string {
  return `${count} ${singular}${count === 1 ? "" : "s"}`;
}
