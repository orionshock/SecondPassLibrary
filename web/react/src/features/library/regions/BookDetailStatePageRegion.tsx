import { Link } from "react-router";

import { ErrorPanel } from "../../../components/ui";

export function BookDetailStatePageRegion({
  state,
  error,
  onRetry,
}: {
  state: "loading" | "not-found" | "error";
  error?: Error;
  onRetry?: () => void;
}) {
  if (state === "loading") {
    return <section className="book-detail-state-region" aria-busy="true">Loading book…</section>;
  }
  if (state === "not-found") {
    return <section className="book-detail-state-region">
      <ErrorPanel>Book not found or unavailable.</ErrorPanel>
      <Link className="button button--secondary" to="/library">Back to Library</Link>
    </section>;
  }
  return <section className="book-detail-state-region">
    <ErrorPanel>{error?.message ?? "The book could not be loaded."}</ErrorPanel>
    <button type="button" onClick={onRetry}>Retry</button>
    <Link className="button button--secondary" to="/library">Back to Library</Link>
  </section>;
}
