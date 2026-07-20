import { Link, Outlet } from "react-router-dom";

export function App() {
  return (
    <div className="app-shell">
      <header>
        <Link to="/">Second Pass Library</Link>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
