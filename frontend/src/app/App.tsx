import {
  classifyApiError,
  getCurrentUser,
  getServerInfo,
  type ApiErrorKind,
  type CurrentUser,
  type ServerInfo,
} from "@second-pass/spl-api";
import { useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router";

import { AppOrchestrator } from "./layout/AppOrchestrator";
import "../components/UiPrimitives.css";

type BootstrapState =
  | { status: "loading" }
  | { status: "ready"; user: CurrentUser; server: ServerInfo }
  | { status: "failed"; kind: ApiErrorKind };

export function App() {
  const location = useLocation();
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<BootstrapState>({ status: "loading" });

  async function refreshCurrentUser(): Promise<CurrentUser> {
    const user = await getCurrentUser();
    setState((current) => current.status === "ready" ? { ...current, user } : current);
    return user;
  }

  async function refreshServerInfo(): Promise<ServerInfo> {
    const server = await getServerInfo();
    setState((current) => current.status === "ready" ? { ...current, server } : current);
    return server;
  }

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
      currentPath={location.pathname}
      onRefreshCurrentUser={refreshCurrentUser}
      onRefreshServerInfo={refreshServerInfo}
      onCurrentUserChange={(user) => {
        setState((current) => current.status === "ready" ? { ...current, user } : current);
      }}
    />
  );
}

export function AppBootstrapView({
  state,
  loginPath,
  onRetry,
  onCurrentUserChange,
  currentPath,
  onRefreshCurrentUser,
  onRefreshServerInfo,
}: {
  state: BootstrapState;
  loginPath: string;
  onRetry: () => void;
  onCurrentUserChange: (user: CurrentUser) => void;
  currentPath?: string;
  onRefreshCurrentUser?: () => Promise<CurrentUser>;
  onRefreshServerInfo?: () => Promise<ServerInfo>;
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

  if (forcedPasswordChangeDestination(state.user, currentPath)) {
    return <Navigate to="/profile/password" replace />;
  }

  return (
    <AppOrchestrator
      user={state.user}
      server={state.server}
      onCurrentUserChange={onCurrentUserChange}
      onRefreshCurrentUser={onRefreshCurrentUser}
      onRefreshServerInfo={onRefreshServerInfo}
    />
  );
}

export type { BootstrapState };

export function forcedPasswordChangeDestination(user: CurrentUser, currentPath?: string): string | undefined {
  return user.mustChangePassword && currentPath && currentPath !== "/profile/password" ? "/profile/password" : undefined;
}
