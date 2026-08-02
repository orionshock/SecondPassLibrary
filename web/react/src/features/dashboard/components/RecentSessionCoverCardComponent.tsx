import type { RecentMarginaliaSession } from "@second-pass/spl-api";
import { Link } from "react-router";

import { breadcrumbNavigationState } from "../../../app/navigation/breadcrumbs";
import { BookCoverComponent } from "../../../shared/books/BookCoverComponent";
import { marginaliaSessionDisplayName } from "../../../shared/marginaliaSessionDisplayName";

export function RecentSessionCoverCardComponent({ item }: { item: RecentMarginaliaSession }) {
  const sessionName = marginaliaSessionDisplayName(item);
  const locationLabel = item.progress?.locationLabel.trim() ? item.progress.locationLabel : null;
  return <article className="dashboard-session-card">
    <Link
      className="dashboard-session-card__session"
      to={`/marginalia/sessions/${encodeURIComponent(item.id)}`}
      aria-label={`${sessionName}, ${item.book.title}`}
      state={breadcrumbNavigationState([{ label: "My Marginalia", to: "/marginalia", resetTrail: true }, { label: sessionName }])}
    >
      <BookCoverComponent coverUrl={item.book.coverUrl} title={item.book.title} />
      <span className="dashboard-session-card__overlay">
        <span className="dashboard-session-card__details">
          <span className="dashboard-session-card__book-title">{item.book.title}</span>
          <span className={`dashboard-session-card__status dashboard-session-card__status--${item.status}`}>{item.status === "active" ? "Active" : "Closed"}</span>
          <strong>{sessionName}</strong>
          <time dateTime={item.lastActivityAt}>{formatRecentActivity(item.lastActivityAt)}</time>
          {locationLabel ? <span className="dashboard-session-card__progress">{locationLabel}</span> : null}
        </span>
      </span>
    </Link>
  </article>;
}

function formatRecentActivity(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(parsed);
}
