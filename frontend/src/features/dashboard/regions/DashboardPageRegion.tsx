import type { RecentMarginaliaSession } from "@second-pass/spl-api";
import { Link } from "react-router";

import { Button, ErrorPanel } from "../../../components/ui";
import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import { ProductPageShell } from "../../../shared/layout/ProductPageShell";
import { DashboardActionTile, type DashboardAction } from "../components/DashboardActionTile";
import { RecentSessionScroller } from "../components/RecentSessionScroller";

export type RecentReadingState =
  | { status: "loading" }
  | { status: "ready"; items: RecentMarginaliaSession[] }
  | { status: "error"; error: Error };

export function DashboardPageRegion({
  bannerText,
  recentReading,
  showAdvancedGroups,
  showImports,
  showUsers,
  showServerSettings,
  onRetryRecentReading,
}: {
  bannerText: string;
  recentReading: RecentReadingState;
  showAdvancedGroups: boolean;
  showImports: boolean;
  showUsers: boolean;
  showServerSettings: boolean;
  onRetryRecentReading: () => void;
}) {
  return <ProductPageShell
    className="dashboard-page"
    title="Library Home"
  >
    {bannerText.trim() ? <aside className="dashboard-banner" aria-label="Server message">{bannerText}</aside> : null}
    <RecentReadingPageRegion state={recentReading} onRetry={onRetryRecentReading} />
    <DashboardLaunchPadsPageRegion showAdvancedGroups={showAdvancedGroups} />
    <DashboardUtilitiesComponent showImports={showImports} showUsers={showUsers} showServerSettings={showServerSettings} />
  </ProductPageShell>;
}

function RecentReadingPageRegion({ state, onRetry }: { state: RecentReadingState; onRetry: () => void }) {
  return <section className="surface dashboard-recent" aria-labelledby="dashboard-recent-title">
    <header className="dashboard-section-header">
      <h2 id="dashboard-recent-title">Recent Sessions</h2>
      {state.status === "ready" && state.items.length > 0
        ? <Link className="button button--small button--secondary" to="/marginalia">View all</Link>
        : null}
    </header>
    {state.status === "loading" ? <p className="dashboard-section-state" aria-live="polite" aria-busy="true">Loading recent reading...</p> : null}
    {state.status === "error" ? <div className="dashboard-section-state">
      <ErrorPanel>{state.error.message}</ErrorPanel>
      <Button type="button" size="small" tone="secondary" onClick={onRetry}>Retry</Button>
    </div> : null}
    {state.status === "ready" && state.items.length === 0 ? <div className="dashboard-section-state dashboard-section-state--empty">
      <MaterialIcon name="auto_stories" size="2rem" />
      <div><p>No recent reading activity yet.</p><p className="muted">Start with a Book from the Library.</p></div>
      <Link className="button button--small button--secondary" to="/library">Browse Library</Link>
    </div> : null}
    {state.status === "ready" && state.items.length > 0 ? <RecentSessionScroller items={state.items} /> : null}
  </section>;
}

const marginaliaActions: DashboardAction[] = [
  { to: "/marginalia", label: "By Session", icon: "history" },
  { to: "/marginalia?view=books", label: "By Book", icon: "menu_book" },
  { to: "/marginalia/import", label: "Import", icon: "upload_file" },
  { to: "/marginalia/export", label: "Export", icon: "download" },
];

function DashboardLaunchPadsPageRegion({ showAdvancedGroups }: { showAdvancedGroups: boolean }) {
  const shelfActions: DashboardAction[] = [
    { to: "/shelves", label: "My Shelves", icon: "shelves" },
    { to: "/shelves?scope=shared", label: "Shared with Me", icon: "share" },
    { to: "/shelves?scope=group", label: "Group Shelves", icon: "group_work" },
    { to: "/shelves/new", label: "Create Shelf", icon: "add" },
  ];
  const libraryActions: DashboardAction[] = [
    { to: "/library", label: "Books", icon: "book_2" },
    { to: "/library?view=authors", label: "Authors", icon: "person" },
    { to: "/library?view=series", label: "Series", icon: "auto_stories" },
    ...(showAdvancedGroups ? [{ to: "/groups", label: "Groups", icon: "groups" }] : []),
  ];

  return <section className="dashboard-launch-pads" aria-label="Dashboard actions">
    <LaunchPad title="My Marginalia" description="Sessions, annotations, import, and export." actions={marginaliaActions} />
    <LaunchPad title="My Shelves" description="Personal and shared shelves." actions={shelfActions} />
    <LaunchPad title="Browse Library" description="Explore the collection." actions={libraryActions} />
  </section>;
}

function LaunchPad({ title, description, actions }: { title: string; description: string; actions: DashboardAction[] }) {
  return <article className="surface dashboard-launch-pad">
    <header>
      <h2>{title}</h2>
      <p>{description}</p>
    </header>
    <nav className={`dashboard-action-grid dashboard-action-grid--count-${actions.length}`} aria-label={`${title} actions`} data-action-count={actions.length}>
      {actions.map((action) => <DashboardActionTile key={action.to} action={action} />)}
    </nav>
  </article>;
}

function DashboardUtilitiesComponent({ showImports, showUsers, showServerSettings }: {
  showImports: boolean;
  showUsers: boolean;
  showServerSettings: boolean;
}) {
  const links = [
    ...(showImports ? [{ to: "/imports", label: "Import Books", icon: "upload_file" }] : []),
    ...(showUsers ? [{ to: "/users", label: "Users", icon: "manage_accounts" }] : []),
    ...(showServerSettings ? [{ to: "/server", label: "Server Settings", icon: "settings" }] : []),
  ];
  if (links.length === 0) return null;

  return <section className="dashboard-server-tools" aria-labelledby="dashboard-server-tools-title">
    <h2 id="dashboard-server-tools-title">Server tools</h2>
    <nav className="dashboard-server-tools__actions" aria-label="Server tools actions">
      {links.map((link) => <Link key={link.to} to={link.to}><MaterialIcon name={link.icon} /><span>{link.label}</span></Link>)}
    </nav>
  </section>;
}
