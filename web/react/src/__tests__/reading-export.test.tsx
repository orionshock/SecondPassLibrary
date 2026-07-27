import type { CurrentUser, Page, ReadingSessionSummary, ServerInfo } from "@second-pass/spl-api";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AppFrame } from "../app/layout/AppFrame";
import { appRoutes } from "../app/router";
import { readingExportBreadcrumbFallback } from "../features/reading/readingBreadcrumbs";
import { ReadingExportOrchestrator } from "../features/reading/ReadingExportOrchestrator";
import { readingExportSelectedBookCount, readingExportSelectedSessions, withReadingExportPageSelection, withReadingExportSessionSelection } from "../features/reading/readingExportSelection";
import { ReadingSessionsOrchestrator } from "../features/reading/ReadingSessionsOrchestrator";
import { ReadingExportPageRegion } from "../features/reading/regions/ReadingExportPageRegion";

const visibleSession: ReadingSessionSummary = {
  id: "session-sensitive-1", bookId: "book-sensitive-1", name: "Morning notes", status: "active", isActive: true,
  startedAt: "2026-07-20T12:00:00Z", completedAt: null, updatedAt: "2026-07-21T12:00:00Z", notes: "", progression: 0.42,
  annotationCount: 2, canOpen: true, book: { id: "book-sensitive-1", title: "Visible Book", coverUrl: "/media/cover.jpg", unavailable: false },
};
const hiddenSession: ReadingSessionSummary = {
  ...visibleSession, id: "session-sensitive-2", bookId: "book-sensitive-2", name: "Recovered history", isActive: false, status: "completed",
  completedAt: "2026-07-22T12:00:00Z", progression: null, canOpen: false, book: { id: null, title: "", coverUrl: null, unavailable: true },
};
const page: Page<ReadingSessionSummary> = { items: [visibleSession, hiddenSession], count: 2, next: null, previous: null };
const user: CurrentUser = { username: "reader", email: "", firstName: "", lastName: "", profileId: "profile", role: "reader", mustChangePassword: false, isOwner: false, isManager: false, isLibrarian: false, isReader: true, canAccessDjangoAdmin: false, groups: [] };
const server: ServerInfo = { name: "SPL", description: "", bannerText: "", advancedLibraryGroupsEnabled: false, publicGroup: { id: "public", name: "Common Room", description: "" }, version: "dev", releaseDate: "" };

function renderExport(selectedSessionIds: ReadonlySet<string> = new Set(), options: { page?: Page<ReadingSessionSummary>; loadError?: Error; selectedError?: Error; completeError?: Error } = {}) {
  return renderToStaticMarkup(<MemoryRouter><ReadingExportPageRegion
    page={options.page ?? page}
    pageNumber={1}
    pageSize={20}
    search=""
    status="all"
    loading={false}
    loadError={options.loadError}
    completeState={{ pending: false, error: options.completeError }}
    selectedState={{ pending: false, error: options.selectedError }}
    selectedSessionIds={selectedSessionIds}
    selectedBookCount={selectedSessionIds.size}
    onSearchChange={vi.fn()}
    onSearch={vi.fn()}
    onStatusChange={vi.fn()}
    onPageChange={vi.fn()}
    onPageSizeChange={vi.fn()}
    onRetry={vi.fn()}
    onCompleteExport={vi.fn()}
    onSessionSelectionChange={vi.fn()}
    onSelectPage={vi.fn()}
    onClearSelection={vi.fn()}
    onSelectedExport={vi.fn()}
  /></MemoryRouter>);
}

describe("My Marginalia Export", () => {
  it("registers the route, breadcrumb, and Session-list action", () => {
    expect(appRoutes[0].children.some((route) => route.path === "reading/export")).toBe(true);
    expect(readingExportBreadcrumbFallback).toEqual([{ label: "My Marginalia", to: "/reading", resetTrail: true }, { label: "Export" }]);
    const listMarkup = renderToStaticMarkup(<MemoryRouter initialEntries={["/reading"]}><Routes><Route element={<AppFrame user={user} server={server} onCurrentUserChange={vi.fn()} />}><Route path="reading" element={<ReadingSessionsOrchestrator />} /></Route></Routes></MemoryRouter>);
    expect(listMarkup).toContain('href="/reading/export"');
    const exportMarkup = renderToStaticMarkup(<MemoryRouter initialEntries={["/reading/export"]}><Routes><Route element={<AppFrame user={user} server={server} onCurrentUserChange={vi.fn()} />}><Route path="reading/export" element={<ReadingExportOrchestrator />} /></Route></Routes></MemoryRouter>);
    expect(exportMarkup).toContain("Complete archive");
  });

  it("renders complete and selective export with safe unavailable-Book rows", () => {
    const markup = renderExport();
    expect(markup).toContain("Morning notes");
    expect(markup).toContain("Visible Book");
    expect(markup).toContain("Recovered history");
    expect(markup).toContain("Book unavailable");
    expect(markup).not.toContain("session-sensitive");
    expect(markup).not.toContain("book-sensitive");
    expect(markup).toContain("Select this page");
    expect(markup).toMatch(/Export selected Sessions<\/button>/);
    expect(markup).toMatch(/disabled=""[^>]*>Export selected Sessions/);
  });

  it("keeps flat Session selection across page/filter-shaped updates", () => {
    let selection = withReadingExportSessionSelection(new Map(), visibleSession, true);
    selection = withReadingExportPageSelection(selection, [hiddenSession], true);
    expect(readingExportSelectedSessions(selection)).toEqual([
      { sessionId: visibleSession.id, bookId: visibleSession.bookId },
      { sessionId: hiddenSession.id, bookId: hiddenSession.bookId },
    ]);
    expect(readingExportSelectedBookCount(selection)).toBe(2);
    expect(withReadingExportPageSelection(selection, [hiddenSession], false).has(visibleSession.id)).toBe(true);
  });

  it("enables selected export for retained selection and keeps errors section-local", () => {
    const markup = renderExport(new Set([visibleSession.id]), { selectedError: new Error("Selected export failed."), completeError: new Error("Complete export failed.") });
    expect(markup).toContain("1 Session selected");
    expect(markup).toContain("Selected export failed.");
    expect(markup).toContain("Complete export failed.");
    expect(markup).not.toMatch(/disabled=""[^>]*>Export selected Sessions/);
  });
});
