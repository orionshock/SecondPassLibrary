import type { CurrentUser, ServerInfo } from "@second-pass/spl-api";
import { Link, NavLink, Outlet } from "react-router-dom";

export interface AppOutletContext {
  currentUser: CurrentUser;
  onCurrentUserChange: (user: CurrentUser) => void;
}

const navigation = [
  { to: "/", label: "Dashboard" },
  { to: "/reading", label: "My Marginalia" },
  { to: "/library", label: "Library" },
  { to: "/groups", label: "Groups" },
  { to: "/shelves", label: "Shelves" },
  { to: "/imports", label: "Import" },
  { to: "/server", label: "Server Settings" },
  { to: "/profile", label: "Profile" },
] as const;

export function AppFrame({
  user,
  server,
  onCurrentUserChange,
}: {
  user: CurrentUser;
  server: ServerInfo;
  onCurrentUserChange: (user: CurrentUser) => void;
}) {
  const displayName = [user.firstName, user.lastName].filter(Boolean).join(" ") || user.username;

  return (
    <div className="app-shell">
      <header className="app-header">
        <Link className="app-identity" to="/">
          <span className="app-mark" aria-hidden="true">SP</span>
          <span>
            <strong>{server.name}</strong>
            <small>{server.description || `Second Pass Library ${server.version}`}</small>
          </span>
        </Link>
        <div className="user-identity">
          <span>
            <strong>{displayName}</strong>
            <small>{user.username} · {user.role}</small>
          </span>
          <a className="logout-link" href="/logout/">Logout</a>
        </div>
      </header>

      {user.bannerText ? <aside className="server-banner">{user.bannerText}</aside> : null}

      <nav className="primary-nav" aria-label="Product UI">
        {navigation.map(({ to, label }) => (
          <NavLink key={to} to={to} end={to === "/"}>{label}</NavLink>
        ))}
      </nav>

      <main className="app-content">
        <Outlet context={{ currentUser: user, onCurrentUserChange } satisfies AppOutletContext} />
      </main>

      <footer className="app-footer">
        <span>{server.name}</span>
        <span>{server.release} · {server.version}</span>
      </footer>
    </div>
  );
}
