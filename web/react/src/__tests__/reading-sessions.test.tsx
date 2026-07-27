import type { Page, ReadingSessionSummary } from "@second-pass/spl-api";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ReadingSessionsPageRegion } from "../features/reading/regions/ReadingSessionsPageRegion";
import { readingImportBreadcrumbFallback } from "../features/reading/readingBreadcrumbs";

const visibleSession: ReadingSessionSummary = {
  id: "9fdd6203-a111-4f17-a477-b9d7ddeec77d",
  bookId: "visible-book",
  name: "Morning notes",
  status: "active",
  isActive: true,
  startedAt: "2026-07-20T12:00:00Z",
  completedAt: null,
  updatedAt: "2026-07-21T12:00:00Z",
  notes: "",
  progression: 0.42,
  annotationCount: 2,
  canOpen: true,
  book: { id: "visible-book", title: "Visible Book", coverUrl: "/media/cover.jpg", unavailable: false },
};

const hiddenSession: ReadingSessionSummary = {
  ...visibleSession,
  id: "79dc1581-5bc4-45ba-81aa-b9198632618e",
  bookId: "hidden-book",
  name: "",
  status: "completed",
  isActive: false,
  completedAt: "2026-07-22T12:00:00Z",
  progression: null,
  annotationCount: 0,
  canOpen: false,
  book: { id: "hidden-book", title: "", coverUrl: null, unavailable: true },
};

function renderRegion(page?: Page<ReadingSessionSummary>, options: { loading?: boolean; error?: Error; search?: string; status?: "all" | "active" | "historical" } = {}) {
  return renderToStaticMarkup(<MemoryRouter><ReadingSessionsPageRegion
    page={page}
    pageNumber={1}
    pageSize={20}
    search={options.search ?? ""}
    status={options.status ?? "all"}
    loading={options.loading ?? false}
    error={options.error}
    onSearchChange={vi.fn()}
    onSearch={vi.fn()}
    onStatusChange={vi.fn()}
    onPageChange={vi.fn()}
    onPageSizeChange={vi.fn()}
    onRetry={vi.fn()}
  /></MemoryRouter>);
}

describe("My Marginalia Session list", () => {
  it("renders visible Book context, history facts, and a correctly named Book action", () => {
    const markup = renderRegion({ items: [visibleSession], count: 1, next: null, previous: null });
    expect(markup).toContain("Morning notes");
    expect(markup).toContain("Visible Book");
    expect(markup).toContain("42% read");
    expect(markup).toContain("2 annotations");
    expect(markup).toContain('href="/library/books/visible-book"');
    expect(markup).toContain(`href="/reading/sessions/${visibleSession.id}"`);
    expect(markup).toContain("View Book");
    expect(markup).not.toContain("Continue reading");
  });

  it("keeps unavailable owned history neutral without leaking identity or an open action", () => {
    const markup = renderRegion({ items: [hiddenSession], count: 1, next: null, previous: null });
    expect(markup).toContain("Unnamed session");
    expect(markup).toContain("Book unavailable");
    expect(markup).not.toContain(">79dc1581");
    expect(markup).toContain(`href="/reading/sessions/${hiddenSession.id}"`);
    expect(markup).not.toContain("hidden-book</");
    expect(markup).not.toContain("View Book");
    expect(markup).not.toContain('href="/library/books/hidden-book"');
  });

  it("renders URL-backed filter controls and the shared pagination frame", () => {
    const markup = renderRegion({ items: [visibleSession], count: 40, next: "/next", previous: null }, { search: "notes", status: "historical" });
    expect(markup).toContain('role="search"');
    expect(markup).toContain('value="notes"');
    expect(markup).toContain('<option value="historical" selected="">Historical</option>');
    expect(markup).toContain('aria-label="Reading sessions pagination, top"');
    expect(markup).toContain('aria-label="Reading sessions pagination, bottom"');
  });

  it("renders bounded loading, filtered empty, and retryable error states", () => {
    expect(renderRegion(undefined, { loading: true })).toContain("Loading reading sessions");
    const empty = renderRegion({ items: [], count: 0, next: null, previous: null }, { search: "missing" });
    expect(empty).toContain("No reading sessions found");
    expect(empty).toContain("clearing the search or status filter");
    const failed = renderRegion(undefined, { error: new Error("Reading history unavailable.") });
    expect(failed).toContain('role="alert"');
    expect(failed).toContain("Retry");
  });

  it("keeps Export absent while exposing Session Detail and the Import destination", () => {
    const markup = renderRegion({ items: [visibleSession], count: 1, next: null, previous: null });
    expect(markup).not.toContain('href="/reading/export"');
    expect(markup).toContain(`/reading/sessions/${visibleSession.id}`);
    expect(readingImportBreadcrumbFallback[0]).toMatchObject({ to: "/reading" });
  });
});
