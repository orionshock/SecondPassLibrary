import type { RecentReadingSession } from "@second-pass/spl-api";
import { Link } from "react-router-dom";

import { Button, ErrorPanel, Surface } from "../../../components/ui";
import { BookCoverComponent } from "../../../shared/books/BookCoverComponent";
import { ProductPageShellComponent } from "../../../shared/layout/ProductPageShellComponent";

export type RecentReadingState =
  | { status: "loading" }
  | { status: "ready"; items: RecentReadingSession[] }
  | { status: "error"; error: Error };

export function DashboardPageRegion({
  description,
  bannerText,
  recentReading,
  showGroups,
  showImports,
  showUsers,
  showServerSettings,
  onRetryRecentReading,
}: {
  description: string;
  bannerText: string;
  recentReading: RecentReadingState;
  showGroups: boolean;
  showImports: boolean;
  showUsers: boolean;
  showServerSettings: boolean;
  onRetryRecentReading: () => void;
}) {
  return <ProductPageShellComponent
    className="dashboard-page"
    eyebrow="Dashboard"
    title="Your reading home"
    description={description.trim() || undefined}
  >
    {bannerText.trim() ? <aside className="dashboard-banner">{bannerText}</aside> : null}
    <RecentReadingPageRegion state={recentReading} onRetry={onRetryRecentReading} />
    <DashboardShortcutsPageRegion
      showGroups={showGroups}
      showImports={showImports}
      showUsers={showUsers}
      showServerSettings={showServerSettings}
    />
  </ProductPageShellComponent>;
}

function RecentReadingPageRegion({ state, onRetry }: { state: RecentReadingState; onRetry: () => void }) {
  return <Surface title="Recent active reading">
    {state.status === "loading" ? <p className="dashboard-section-state" aria-live="polite" aria-busy="true">Loading recent reading...</p> : null}
    {state.status === "error" ? <div className="dashboard-section-state">
      <ErrorPanel>{state.error.message}</ErrorPanel>
      <Button type="button" size="small" tone="secondary" onClick={onRetry}>Retry</Button>
    </div> : null}
    {state.status === "ready" && state.items.length === 0 ? <div className="dashboard-section-state">
      <p>No active reading sessions.</p>
      <Link className="button button--small button--secondary" to="/library">Browse Library</Link>
    </div> : null}
    {state.status === "ready" && state.items.length > 0 ? <div className="dashboard-recent-list">
      {state.items.map((item) => <RecentReadingCardComponent key={item.session.id} item={item} />)}
    </div> : null}
  </Surface>;
}

function RecentReadingCardComponent({ item }: { item: RecentReadingSession }) {
  const progression = item.session.progression === null
    ? undefined
    : Math.round(Math.max(0, Math.min(1, item.session.progression)) * 100);
  return <Link className="dashboard-reading-card" to={`/library/books/${encodeURIComponent(item.book.id)}`}>
    <BookCoverComponent coverUrl={item.book.coverUrl} title={item.book.title} />
    <span className="dashboard-reading-card__body">
      <strong>{item.book.title}</strong>
      {item.session.name ? <span>{item.session.name}</span> : null}
      <time dateTime={item.lastActivityAt}>{formatRecentActivity(item.lastActivityAt)}</time>
      {progression === undefined ? null : <span>{progression}% read</span>}
    </span>
  </Link>;
}

function DashboardShortcutsPageRegion({ showGroups, showImports, showUsers, showServerSettings }: {
  showGroups: boolean;
  showImports: boolean;
  showUsers: boolean;
  showServerSettings: boolean;
}) {
  return <div className="dashboard-shortcuts" aria-label="Dashboard shortcuts">
    <ShortcutGroup title="Library" links={[
      { to: "/library", label: "Books" },
      { to: "/library?view=authors", label: "Authors" },
      { to: "/library?view=series", label: "Series" },
      ...(showGroups ? [{ to: "/groups", label: "Groups" }] : []),
      ...(showImports ? [{ to: "/imports", label: "Import Books" }] : []),
    ]} />
    <ShortcutGroup title="Shelves" links={[
      { to: "/shelves", label: "View Shelves" },
      { to: "/shelves/new", label: "Create Shelf" },
    ]} />
    {showUsers || showServerSettings ? <ShortcutGroup title="Manage" links={[
      ...(showUsers ? [{ to: "/users", label: "Users" }] : []),
      ...(showServerSettings ? [{ to: "/server", label: "Server Settings" }] : []),
    ]} /> : null}
  </div>;
}

function ShortcutGroup({ title, links }: { title: string; links: Array<{ to: string; label: string }> }) {
  return <Surface title={title}>
    <nav className="dashboard-shortcut-links" aria-label={`${title} shortcuts`}>
      {links.map((link) => <Link key={link.to} to={link.to}>{link.label}</Link>)}
    </nav>
  </Surface>;
}

function formatRecentActivity(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
}
