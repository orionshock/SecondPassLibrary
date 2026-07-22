import {
  canSeeImports,
  canSeeServerSettings,
  canSeeUsers,
  type CurrentUser,
  type ServerInfo,
} from "@second-pass/spl-api";
import { useCallback, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

import { BreadcrumbsComponent } from "../navigation/BreadcrumbsComponent";
import type { BreadcrumbItem } from "../navigation/breadcrumbs";
import "./AppFrame.css";

export interface AppOutletContext {
  currentUser: CurrentUser;
  serverInfo: ServerInfo;
  onCurrentUserChange: (user: CurrentUser) => void;
  onServerInfoChange: (server: ServerInfo) => void;
  refreshCurrentUser: () => Promise<CurrentUser>;
  setBreadcrumbs: (pathname: string, items: readonly BreadcrumbItem[]) => void;
}

const navigation = [
  { to: "/", label: "Dashboard" },
  { to: "/reading", label: "My Marginalia" },
  { to: "/library", label: "Library" },
  { to: "/groups", label: "Groups", visible: (user: CurrentUser) => user.advancedLibraryGroupsEnabled },
  { to: "/shelves", label: "Shelves" },
  { to: "/imports", label: "Imports", visible: canSeeImports },
  { to: "/users", label: "Users", visible: canSeeUsers },
  { to: "/server", label: "Server Settings", visible: canSeeServerSettings },
] as const;

export function AppFrame({
  user,
  server,
  onCurrentUserChange,
  onServerInfoChange = () => undefined,
  onRefreshCurrentUser = async () => user,
}: {
  user: CurrentUser;
  server: ServerInfo;
  onCurrentUserChange: (user: CurrentUser) => void;
  onServerInfoChange?: (server: ServerInfo) => void;
  onRefreshCurrentUser?: () => Promise<CurrentUser>;
}) {
  const location = useLocation();
  const [breadcrumbRegistration, setBreadcrumbRegistration] = useState<{ pathname: string; items: readonly BreadcrumbItem[] }>();
  const setBreadcrumbs = useCallback((pathname: string, items: readonly BreadcrumbItem[]) => {
    setBreadcrumbRegistration({ pathname, items });
  }, []);
  const breadcrumbs = breadcrumbRegistration?.pathname === location.pathname ? breadcrumbRegistration.items : [];

  return (
    <div className="app-shell">
      <header className="app-header">
        <Link className="app-identity" to="/">
          <img src="/static/web/favicon.png" width="28" height="28" alt="" aria-hidden="true" />
          <strong>{server.name}</strong>
        </Link>

        <nav className="primary-nav" aria-label="Product UI">
          {navigation.filter((item) => !("visible" in item) || item.visible(user)).map(({ to, label }) => (
            <NavLink key={to} to={to} end={to === "/"}>{label}</NavLink>
          ))}
        </nav>

        <div className="user-actions">
          <Link className="profile-link" to="/profile">{user.username}</Link>
          <a className="logout-link" href="/logout/">Logout</a>
        </div>
      </header>

      {user.bannerText ? <aside className="server-banner">{user.bannerText}</aside> : null}

      <BreadcrumbsComponent items={breadcrumbs} />

      <main className="app-content">
        <Outlet context={{ currentUser: user, serverInfo: server, onCurrentUserChange, onServerInfoChange, refreshCurrentUser: onRefreshCurrentUser, setBreadcrumbs } satisfies AppOutletContext} />
      </main>

      <footer className="app-footer">
        <span>Second Pass Library</span>
        <span>{server.version}</span>
      </footer>
    </div>
  );
}
