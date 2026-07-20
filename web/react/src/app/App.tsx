import {
  classifyApiError,
  getCurrentUser,
  getServerInfo,
  type ApiErrorKind,
  type CurrentUser,
  type ServerInfo,
} from "@second-pass/spl-api";
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

import { AppFrame } from "./layout/AppFrame";

type BootstrapState =
  | { status: "loading" }
  | { status: "ready"; user: CurrentUser; server: ServerInfo }
  | { status: "failed"; kind: ApiErrorKind };

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
}: {
  state: BootstrapState;
  loginPath: string;
  onRetry: () => void;
  onCurrentUserChange: (user: CurrentUser) => void;
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

  return (
    <AppFrame
      user={state.user}
      server={state.server}
      onCurrentUserChange={onCurrentUserChange}
    />
  );
}

export type { BootstrapState };
