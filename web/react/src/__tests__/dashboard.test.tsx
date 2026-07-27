import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { RecentReadingSession } from "@second-pass/spl-api";
import { DASHBOARD_RECENT_READING_LIMIT } from "../features/dashboard/DashboardOrchestrator";
import { DashboardPageRegion, type RecentReadingState } from "../features/dashboard/regions/DashboardPageRegion";

const recentItem: RecentReadingSession = {
  lastActivityAt: "2026-07-27T18:30:00Z",
  session: {
    id: "session-1",
    name: "Evening read",
    status: "active",
    isActive: true,
    progression: 0.42,
  },
  book: {
    id: "book/id",
    title: "A Book",
    coverUrl: "/media/cover.jpg",
  },
};

function renderDashboard(
  recentReading: RecentReadingState,
  overrides: Partial<Parameters<typeof DashboardPageRegion>[0]> = {},
): string {
  return renderToStaticMarkup(<MemoryRouter><DashboardPageRegion
    description="A family server."
    bannerText="Maintenance tonight."
    recentReading={recentReading}
    showGroups
    showImports
    showUsers
    showServerSettings
    onRetryRecentReading={vi.fn()}
    {...overrides}
  /></MemoryRouter>);
}

describe("Dashboard", () => {
  it("uses the bounded recent-reading request contract", () => {
    expect(DASHBOARD_RECENT_READING_LIMIT).toBe(10);
  });

  it("renders server description and a nonblank Dashboard-only banner", () => {
    const markup = renderDashboard({ status: "loading" });
    expect(markup).toContain("Your reading home");
    expect(markup).toContain("A family server.");
    expect(markup).toContain("Maintenance tonight.");
    expect(renderDashboard({ status: "loading" }, { bannerText: "  \n " })).not.toContain("dashboard-banner");
  });

  it("keeps recent-reading loading, empty, and failure states inside the section", () => {
    expect(renderDashboard({ status: "loading" })).toContain("Loading recent reading");
    const empty = renderDashboard({ status: "ready", items: [] });
    expect(empty).toContain("No active reading sessions.");
    expect(empty).toContain('href="/library"');

    const failed = renderDashboard({ status: "error", error: new Error("Recent reading failed.") });
    expect(failed).toContain("Recent reading failed.");
    expect(failed).toContain("Retry");
    expect(failed).toContain("Maintenance tonight.");
    expect(failed).toContain("View Shelves");
  });

  it("renders recent session facts and links to Session Detail", () => {
    const markup = renderDashboard({ status: "ready", items: [recentItem] });
    expect(markup).toContain("A Book");
    expect(markup).toContain("Evening read");
    expect(markup).toContain("42% read");
    expect(markup).toContain('dateTime="2026-07-27T18:30:00Z"');
    expect(markup).toContain('src="/media/cover.jpg"');
    expect(markup).toContain('href="/reading/sessions/session-1"');
    expect(markup).not.toContain('href="/library/books/book%2Fid"');
  });

  it("renders the cover fallback when a recent Book has no cover", () => {
    const markup = renderDashboard({ status: "ready", items: [{
      ...recentItem,
      book: { ...recentItem.book, coverUrl: null },
    }] });
    expect(markup).toContain("No cover available for A Book");
  });

  it("shows only the enabled role- and mode-aware shortcuts", () => {
    const all = renderDashboard({ status: "ready", items: [] });
    for (const label of ["Groups", "Import Books", "Users", "Server Settings"]) expect(all).toContain(label);
    expect(all).not.toContain("My Marginalia");

    const reader = renderDashboard({ status: "ready", items: [] }, {
      showGroups: false,
      showImports: false,
      showUsers: false,
      showServerSettings: false,
    });
    for (const label of ["Groups", "Import Books", "Users", "Server Settings", "Manage shortcuts"]) expect(reader).not.toContain(label);
    for (const label of ["Books", "Authors", "Series", "View Shelves", "Create Shelf"]) expect(reader).toContain(label);
  });
});
