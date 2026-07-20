import {
  classifyApiError,
  getCurrentUser,
  getServerInfo,
  type ApiErrorKind,
  type CurrentUser,
  type ServerInfo,
} from "@second-pass/spl-api";
import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

type BootstrapState =
  | { status: "loading" }
  | { status: "ready"; user: CurrentUser; server: ServerInfo }
  | { status: "failed"; kind: ApiErrorKind };

const navigation = [
  { to: "/", label: "Dashboard" },
  { to: "/library", label: "Library" },
  { to: "/groups", label: "Groups" },
  { to: "/shelves", label: "Shelves" },
  { to: "/users", label: "Users" },
  { to: "/imports", label: "Imports" },
  { to: "/server", label: "Server Settings" },
] as const;

export function App() {
  const location = useLocation();
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<BootstrapState>({ status: "loading" });

  useEffect(() => {
    let active = true;
    setState({ status: "loading" });
    Promise.all([getCurrentUser(), getServerInfo()])
      .then(([user, server]) => {
        if (active) setState({ status: "ready", user, server });
      })
      .catch((error: unknown) => {
        if (active) setState({ status: "failed", kind: classifyApiError(error) });
      });
    return () => {
      active = false;
    };
  }, [attempt]);

  return (
    <AppBootstrapView
      state={state}
      loginPath={`/login/?next=${encodeURIComponent(`${location.pathname}${location.search}`)}`}
      onRetry={() => setAttempt((current) => current + 1)}
    />
  );
}

export function AppBootstrapView({
  state,
  loginPath,
  onRetry,
}: {
  state: BootstrapState;
  loginPath: string;
  onRetry: () => void;
}) {
  if (state.status === "loading") {
    return (
      <main className="bootstrap-panel" aria-live="polite" aria-busy="true">
        <p className="eyebrow">Second Pass Library</p>
        <h1>Opening your library</h1>
        <p>Loading your account and server details.</p>
      </main>
    );
  }

  if (state.status === "failed" && state.kind === "authentication") {
    return (
      <main className="bootstrap-panel" role="alert">
        <p className="eyebrow">Session required</p>
        <h1>Sign in to continue</h1>
        <a className="button-link" href={loginPath}>Log in</a>
      </main>
    );
  }

  if (state.status === "failed") {
    return (
      <main className="bootstrap-panel" role="alert">
        <p className="eyebrow">Unable to load</p>
        <h1>Your library is temporarily unavailable</h1>
        <p>Check the server connection, then try again.</p>
        <button type="button" onClick={onRetry}>Retry</button>
      </main>
    );
  }

  return <AppLayout user={state.user} server={state.server} />;
}

export function AppLayout({ user, server }: { user: CurrentUser; server: ServerInfo }) {
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
          <a href="/logout/">Logout</a>
        </div>
      </header>

      {user.bannerText ? <aside className="server-banner">{user.bannerText}</aside> : null}

      <nav className="primary-nav" aria-label="Product UI">
        {navigation.map(({ to, label }) => (
          <NavLink key={to} to={to} end={to === "/"}>{label}</NavLink>
        ))}
      </nav>

      <main className="app-content">
        <Outlet />
      </main>
    </div>
  );
}

export type { BootstrapState };
