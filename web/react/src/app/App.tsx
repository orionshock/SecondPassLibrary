import { getCurrentUser, type CurrentUser } from "@second-pass/spl-api";
import { useEffect, useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";

export function App() {
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    getCurrentUser()
      .then((user) => {
        if (active) setCurrentUser(user);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, []);

  if (failed) {
    return (
      <main className="session-state">
        <h1>Session unavailable</h1>
        <p>Your session may have expired.</p>
        <a href="/login/?next=/">Log in</a>
      </main>
    );
  }

  if (!currentUser) {
    return <main className="session-state">Loading your library...</main>;
  }

  return (
    <div className="app-shell">
      <header>
        <Link to="/">Second Pass Library</Link>
        <span>{currentUser.username} · {currentUser.role}</span>
      </header>
      {currentUser.bannerText ? <p className="server-banner">{currentUser.bannerText}</p> : null}
      <nav aria-label="Product UI">
        {[
          ["/", "Dashboard"],
          ["/library/", "Library"],
          ["/shelves/", "Shelves"],
          ["/groups/", "Groups"],
          ["/imports/", "Imports"],
          ["/users/", "Users"],
          ["/settings/", "Settings"],
        ].map(([to, label]) => <NavLink key={to} to={to}>{label}</NavLink>)}
      </nav>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
