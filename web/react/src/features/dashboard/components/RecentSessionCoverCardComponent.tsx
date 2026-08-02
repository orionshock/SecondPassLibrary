import type { RecentMarginaliaSession } from "@second-pass/spl-api";
import { Link } from "react-router";

import { breadcrumbNavigationState } from "../../../app/navigation/breadcrumbs";
import { BookCoverComponent } from "../../../shared/books/BookCoverComponent";
import { marginaliaSessionDisplayName } from "../../../shared/marginaliaSessionDisplayName";

export function RecentSessionCoverCardComponent({ item }: { item: RecentMarginaliaSession }) {
  const sessionName = marginaliaSessionDisplayName(item);
  return <article className="dashboard-session-card">
    <Link
      className="dashboard-session-card__session"
      to={`/marginalia/sessions/${encodeURIComponent(item.id)}`}
      aria-label={`${sessionName}, ${item.book.title}`}
      state={breadcrumbNavigationState([{ label: "My Marginalia", to: "/marginalia", resetTrail: true }, { label: sessionName }])}
    >
      <BookCoverComponent coverUrl={item.book.coverUrl} title={item.book.title} />
      <span className="dashboard-session-card__overlay">
        <span className={`dashboard-session-card__status dashboard-session-card__status--${item.status}`}>{item.status === "active" ? "Active" : "Closed"}</span>
        <strong>{sessionName}</strong>
        <span className="dashboard-session-card__book-title">{item.book.title}</span>
        <time dateTime={item.lastActivityAt}>{formatRecentActivity(item.lastActivityAt)}</time>
      </span>
    </Link>
    {item.book.canOpen ? <Link className="dashboard-session-card__book-link" to={`/library/books/${encodeURIComponent(item.book.id)}`}>View Book</Link> : null}
  </article>;
}

function formatRecentActivity(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(parsed);
}
