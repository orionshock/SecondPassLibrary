import type { Page, ReadingSessionSummary } from "@second-pass/spl-api";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { MarginaliaSessionsPageRegion } from "../features/marginalia/regions/MarginaliaSessionsPageRegion";
import { marginaliaExportBreadcrumbFallback, marginaliaImportBreadcrumbFallback } from "../features/marginalia/marginaliaBreadcrumbs";
import { marginaliaSessionNoteExcerpt } from "../features/marginalia/marginaliaSessionNoteExcerpt";
import { marginaliaSessionDisplayName } from "../shared/marginaliaSessionDisplayName";

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
  return renderToStaticMarkup(<MemoryRouter><MarginaliaSessionsPageRegion
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
    expect(markup).toContain(`href="/marginalia/sessions/${visibleSession.id}"`);
    expect(markup).toContain("View Book");
    expect(markup).not.toContain("Continue reading");
  });

  it("keeps unavailable owned history neutral without leaking identity or an open action", () => {
    const markup = renderRegion({ items: [hiddenSession], count: 1, next: null, previous: null });
    expect(markup).toContain("Unnamed Session 32618e");
    expect(markup).toContain("Book unavailable");
    expect(markup).not.toContain(">79dc1581");
    expect(markup).toContain(`href="/marginalia/sessions/${hiddenSession.id}"`);
    expect(markup).not.toContain("hidden-book</");
    expect(markup).not.toContain("View Book");
    expect(markup).not.toContain('href="/library/books/hidden-book"');
  });

  it("uses returned Session names unchanged and derives only blank display names", () => {
    expect(marginaliaSessionDisplayName(visibleSession)).toBe("Morning notes");
    expect(marginaliaSessionDisplayName(hiddenSession)).toBe("Unnamed Session 32618e");
  });

  it("renders a collapsed note excerpt between Session facts and the Book action", () => {
    const rawNote = "  First line\n\tSecond line   with spacing  ";
    const markup = renderRegion({ items: [{ ...visibleSession, notes: rawNote }], count: 1, next: null, previous: null });
    const excerpt = "First line Second line with spacing";
    expect(markup).toContain(excerpt);
    expect(markup.indexOf("2 annotations")).toBeLessThan(markup.indexOf(excerpt));
    expect(markup.indexOf(excerpt)).toBeLessThan(markup.indexOf("View Book"));
    expect(rawNote).toBe("  First line\n\tSecond line   with spacing  ");
  });

  it("bounds note excerpts without decorating short or blank notes", () => {
    const exact = "x".repeat(120);
    expect(marginaliaSessionNoteExcerpt(exact)).toBe(exact);
    expect(marginaliaSessionNoteExcerpt(`${exact}y`)).toBe(`${exact}…`);
    expect(marginaliaSessionNoteExcerpt(" \n\t  ")).toBeUndefined();
    const blankMarkup = renderRegion({ items: [{ ...visibleSession, notes: " \n\t " }], count: 1, next: null, previous: null });
    expect(blankMarkup).not.toContain("…");
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

  it("exposes Session Detail and implemented Import/Export destinations", () => {
    const markup = renderRegion({ items: [visibleSession], count: 1, next: null, previous: null });
    expect(markup).toContain(`/marginalia/sessions/${visibleSession.id}`);
    expect(marginaliaImportBreadcrumbFallback[0]).toMatchObject({ to: "/marginalia" });
    expect(marginaliaExportBreadcrumbFallback[0]).toMatchObject({ to: "/marginalia" });
  });
});
