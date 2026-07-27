import type { ReadingSessionSummary } from "@second-pass/spl-api";
import { Link } from "react-router-dom";

import { Badge } from "../../../components/ui";
import { breadcrumbNavigationState } from "../../../app/navigation/breadcrumbs";
import { BookCoverComponent } from "../../../shared/books/BookCoverComponent";
import { readingSessionBreadcrumbFallback } from "../readingBreadcrumbs";

export function SessionSummaryRowComponent({ session }: { session: ReadingSessionSummary }) {
  const sessionName = session.name.trim() || "Unnamed session";
  const bookTitle = session.book.unavailable ? "Book unavailable" : session.book.title || "Untitled book";
  const relevantDate = session.completedAt ?? session.updatedAt ?? session.startedAt;

  return <article className="reading-session-row">
    <div className="reading-session-row__cover">
      <BookCoverComponent coverUrl={session.book.coverUrl} title={bookTitle} />
    </div>
    <div className="reading-session-row__body">
      <div className="reading-session-row__heading">
        <h2><Link to={`/reading/sessions/${encodeURIComponent(session.id)}`} state={breadcrumbNavigationState(readingSessionBreadcrumbFallback(sessionName))}>{sessionName}</Link></h2>
        <Badge tone={session.isActive ? "success" : "default"}>{session.isActive ? "Active" : "Historical"}</Badge>
      </div>
      {session.book.unavailable
        ? <p className="reading-session-row__book reading-session-row__book--unavailable">Book unavailable</p>
        : <p className="reading-session-row__book">{bookTitle}</p>}
      <div className="reading-session-row__facts">
        <span>{session.completedAt ? "Completed" : "Updated"} <time dateTime={relevantDate}>{formatDate(relevantDate)}</time></span>
        {session.progression !== null ? <><span className="css-dot" aria-hidden="true" /><span>{formatProgression(session.progression)} read</span></> : null}
        <span className="css-dot" aria-hidden="true" /><span>{formatCount(session.annotationCount, "annotation")}</span>
      </div>
    </div>
    {session.canOpen && session.book.id ? <Link className="button button--small button--secondary reading-session-row__book-link" to={`/library/books/${encodeURIComponent(session.book.id)}`}>View Book</Link> : null}
  </article>;
}

function formatDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Unknown date";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(parsed);
}

function formatProgression(value: number): string {
  return `${Math.round(Math.min(1, Math.max(0, value)) * 100)}%`;
}

function formatCount(count: number, singular: string): string {
  return `${count} ${singular}${count === 1 ? "" : "s"}`;
}
