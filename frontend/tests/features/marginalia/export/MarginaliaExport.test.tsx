import { MarginaliaExportTooLargeError, type CurrentUser, type MarginaliaSessionListItem, type Page, type ServerInfo } from "@second-pass/spl-api";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { AppOrchestrator } from "../../../../src/app/layout/AppOrchestrator";
import { appRoutes } from "../../../../src/app/router";
import { marginaliaExportBreadcrumbFallback } from "../../../../src/features/marginalia/marginaliaBreadcrumbs";
import { marginaliaExportLimitFailure, MarginaliaExportOrchestrator } from "../../../../src/features/marginalia/export/MarginaliaExportOrchestrator";
import { marginaliaExportSelectedBookCount, marginaliaExportSelectedSessionIds, withMarginaliaExportPageSelection, withMarginaliaExportSessionSelection } from "../../../../src/features/marginalia/export/marginaliaExportSelection";
import { MarginaliaSessionsOrchestrator } from "../../../../src/features/marginalia/browse/MarginaliaSessionsOrchestrator";
import { MarginaliaExportPageRegion, type MarginaliaExportLimitFailure } from "../../../../src/features/marginalia/export/MarginaliaExportPageRegion";

const visibleSession: MarginaliaSessionListItem = {
  id: "session-sensitive-1", name: "Morning notes", status: "active",
  startedAt: "2026-07-20T12:00:00Z", closedAt: null, updatedAt: "2026-07-21T12:00:00Z",
  lastActivityAt: "2026-07-21T12:00:00Z", notes: "", annotationCount: 2,
  book: { id: "book-sensitive-1", title: "Visible Book", coverUrl: "/media/cover.jpg", canOpen: true },
};
const hiddenSession: MarginaliaSessionListItem = {
  ...visibleSession, id: "session-sensitive-2", name: "Recovered history", status: "closed",
  closedAt: "2026-07-22T12:00:00Z",
  book: { id: "book-sensitive-2", title: "Remembered Book", coverUrl: null, canOpen: false },
};
const page: Page<MarginaliaSessionListItem> = { items: [visibleSession, hiddenSession], count: 2, next: null, previous: null };
const user: CurrentUser = { username: "reader", email: "", firstName: "", lastName: "", profileId: "profile", role: "reader", mustChangePassword: false, isOwner: false, isManager: false, isLibrarian: false, isReader: true, canAccessDjangoAdmin: false, groups: [] };
const server: ServerInfo = { name: "SPL", description: "", bannerText: "", advancedLibraryGroupsEnabled: false, secondPassReaderWebClientUrl: null, marginaliaProfileUri: "profile", publicGroup: { id: "public", name: "Common Room", description: "" }, version: "dev", releaseDate: "" };

function renderExport(selectedSessionIds: ReadonlySet<string> = new Set(), options: { page?: Page<MarginaliaSessionListItem>; loadError?: Error; selectedError?: Error; completeError?: Error; selectedLimitFailure?: MarginaliaExportLimitFailure; completeLimitFailure?: MarginaliaExportLimitFailure } = {}) {
  return renderToStaticMarkup(<MemoryRouter><MarginaliaExportPageRegion
    page={options.page ?? page}
    pageNumber={1}
    pageSize={20}
    search=""
    status="all"
    loading={false}
    loadError={options.loadError}
    completeState={{ pending: false, error: options.completeError }}
    completeLimitFailure={options.completeLimitFailure}
    selectedState={{ pending: false, error: options.selectedError }}
    selectedLimitFailure={options.selectedLimitFailure}
    selectedSessionIds={selectedSessionIds}
    selectedBookCount={selectedSessionIds.size}
    includeEmptySessions={false}
    onIncludeEmptySessionsChange={vi.fn()}
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
    expect(appRoutes[0].children.some((route) => route.path === "marginalia/export")).toBe(true);
    expect(marginaliaExportBreadcrumbFallback).toEqual([{ label: "My Marginalia", to: "/marginalia", resetTrail: true }, { label: "Export" }]);
    const listMarkup = renderToStaticMarkup(<MemoryRouter initialEntries={["/marginalia"]}><Routes><Route element={<AppOrchestrator user={user} server={server} onCurrentUserChange={vi.fn()} />}><Route path="marginalia" element={<MarginaliaSessionsOrchestrator />} /></Route></Routes></MemoryRouter>);
    expect(listMarkup).toContain('href="/marginalia/export"');
    const exportMarkup = renderToStaticMarkup(<MemoryRouter initialEntries={["/marginalia/export"]}><Routes><Route element={<AppOrchestrator user={user} server={server} onCurrentUserChange={vi.fn()} />}><Route path="marginalia/export" element={<MarginaliaExportOrchestrator />} /></Route></Routes></MemoryRouter>);
    expect(exportMarkup).toContain("<h1>Export Marginalia</h1>");
    expect(exportMarkup).toContain('aria-label="My Marginalia sections"');
    expect(exportMarkup).toContain("Complete archive");
  });

  it("renders canonical active/closed candidates and keeps inaccessible Book identity", () => {
    const markup = renderExport();
    expect(markup).toContain("Morning notes");
    expect(markup).toContain("Visible Book");
    expect(markup).toContain("Recovered history");
    expect(markup).toContain("Remembered Book");
    expect(markup).toContain("Closed");
    expect(markup).not.toContain("% read");
    expect(markup).not.toContain(`/library/books/${hiddenSession.book.id}`);
    expect(markup).not.toContain("session-sensitive");
    expect(markup).not.toContain("book-sensitive");
    expect(markup).toContain("Select this page");
    expect(markup).toContain("Include empty sessions");
    expect(markup).toMatch(/Export selected Sessions<\/button>/);
    expect(markup).toMatch(/disabled=""[^>]*>Export selected Sessions/);
  });

  it("keeps flat Session selection across page/filter-shaped updates", () => {
    let selection = withMarginaliaExportSessionSelection(new Map(), visibleSession, true);
    selection = withMarginaliaExportPageSelection(selection, [hiddenSession], true);
    expect(marginaliaExportSelectedSessionIds(selection)).toEqual([visibleSession.id, hiddenSession.id]);
    expect(marginaliaExportSelectedBookCount(selection)).toBe(2);
    expect(withMarginaliaExportPageSelection(selection, [hiddenSession], false).has(visibleSession.id)).toBe(true);
  });

  it("enables selected export for retained selection and keeps errors section-local", () => {
    const markup = renderExport(new Set([visibleSession.id]), { selectedError: new Error("Selected export failed."), completeError: new Error("Complete export failed.") });
    expect(markup).toContain("1 Session selected");
    expect(markup).toContain("Selected export failed.");
    expect(markup).toContain("Complete export failed.");
    expect(markup).not.toMatch(/disabled=""[^>]*>Export selected Sessions/);
  });

  it("shows actionable oversized-export guidance in the affected section", () => {
    const failure: MarginaliaExportLimitFailure = {
      message: "The Marginalia export is too large.",
      guidance: "Choose fewer Sessions and try the export again.",
      limitLabel: "Maximum: 50,000 annotations.",
    };
    const markup = renderExport(new Set([visibleSession.id]), {
      selectedError: new Error(failure.message),
      selectedLimitFailure: failure,
    });

    expect(markup).toContain(failure.message);
    expect(markup).toContain(failure.guidance);
    expect(markup).toContain(failure.limitLabel);
    expect(markup).toContain("Export selected Sessions");
  });

  it("maps the SDK limit error at the Export orchestrator boundary", () => {
    expect(marginaliaExportLimitFailure(new MarginaliaExportTooLargeError({
      message: "The Marginalia export is too large.",
      guidance: "Use Selected Sessions and choose fewer Sessions, then try again.",
      exportMode: "full",
      limitKind: "archive_bytes",
      maximum: 16 * 1024 * 1024,
    }))).toEqual({
      message: "The Marginalia export is too large.",
      guidance: "Use Selected Sessions and choose fewer Sessions, then try again.",
      limitLabel: "Maximum archive size: 16 MiB.",
    });
    expect(marginaliaExportLimitFailure(new Error("Other failure"))).toBeUndefined();
  });
});

