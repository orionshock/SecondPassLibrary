import type { CurrentUser, ServerInfo } from "@second-pass/spl-api";
import { Link, NavLink, Outlet } from "react-router-dom";

import "./AppFrame.css";

export interface AppOutletContext {
  currentUser: CurrentUser;
  onCurrentUserChange: (user: CurrentUser) => void;
  refreshCurrentUser: () => Promise<CurrentUser>;
}

const navigation = [
  { to: "/", label: "Dashboard" },
  { to: "/reading", label: "My Marginalia" },
  { to: "/library", label: "Library" },
  { to: "/groups", label: "Groups" },
  { to: "/shelves", label: "Shelves" },
  { to: "/imports", label: "Import" },
  { to: "/server", label: "Server Settings" },
] as const;

export function AppFrame({
  user,
  server,
  onCurrentUserChange,
  onRefreshCurrentUser = async () => user,
}: {
  user: CurrentUser;
  server: ServerInfo;
  onCurrentUserChange: (user: CurrentUser) => void;
  onRefreshCurrentUser?: () => Promise<CurrentUser>;
}) {
  return (
    <div className="app-shell">
      <header className="app-header">
        <Link className="app-identity" to="/">
          <img src="/static/web/favicon.png" width="28" height="28" alt="" aria-hidden="true" />
          <strong>{server.name}</strong>
        </Link>

        <nav className="primary-nav" aria-label="Product UI">
          {navigation.map(({ to, label }) => (
            <NavLink key={to} to={to} end={to === "/"}>{label}</NavLink>
          ))}
        </nav>

        <div className="user-actions">
          <Link className="profile-link" to="/profile">{user.username}</Link>
          <a className="logout-link" href="/logout/">Logout</a>
        </div>
      </header>

      {user.bannerText ? <aside className="server-banner">{user.bannerText}</aside> : null}

      <main className="app-content">
        <Outlet context={{ currentUser: user, onCurrentUserChange, refreshCurrentUser: onRefreshCurrentUser } satisfies AppOutletContext} />
      </main>

      <footer className="app-footer">
        <span>Second Pass Library</span>
        <span>{server.version}</span>
      </footer>
    </div>
  );
}
