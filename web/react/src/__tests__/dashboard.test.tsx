import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { RecentMarginaliaSession } from "@second-pass/spl-api";
import { DASHBOARD_RECENT_QUERY, DASHBOARD_RECENT_READING_LIMIT } from "../features/dashboard/DashboardOrchestrator";
import { dashboardScrollerState, scrollDashboardScroller } from "../features/dashboard/components/RecentSessionScrollerComponent";
import { DashboardPageRegion, type RecentReadingState } from "../features/dashboard/regions/DashboardPageRegion";

const recentItem: RecentMarginaliaSession = {
  id: "session-1",
  name: "Evening read",
  status: "active",
  lastActivityAt: "2026-07-27T18:30:00Z",
  book: {
    id: "book/id",
    title: "A Book",
    coverUrl: "/media/cover.jpg",
    canOpen: true,
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
  it("uses the canonical bounded active-only recent Marginalia request", () => {
    expect(DASHBOARD_RECENT_READING_LIMIT).toBe(10);
    expect(DASHBOARD_RECENT_QUERY).toEqual({ limit: 10 });
    expect(DASHBOARD_RECENT_QUERY).not.toHaveProperty("includeClosed");
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
    expect(empty).toContain("No recent reading activity yet.");
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
    expect(markup).toContain('dateTime="2026-07-27T18:30:00Z"');
    expect(markup).toContain('src="/media/cover.jpg"');
    expect(markup).toContain('href="/marginalia/sessions/session-1"');
    expect(markup).toContain('href="/library/books/book%2Fid"');
    expect(markup).toContain("Active");
    expect(markup).not.toContain("Open in Reader");
  });

  it("renders canonical closed Session status when supplied by the SDK boundary", () => {
    const markup = renderDashboard({ status: "ready", items: [{ ...recentItem, status: "closed" }] });
    expect(markup).toContain("Closed");
    expect(markup).toContain('href="/marginalia/sessions/session-1"');
  });

  it("keeps inaccessible Book identity without a dead Library action", () => {
    const markup = renderDashboard({ status: "ready", items: [{
      ...recentItem,
      book: { ...recentItem.book, title: "Remembered Book", canOpen: false },
    }] });
    expect(markup).toContain("Remembered Book");
    expect(markup).toContain('src="/media/cover.jpg"');
    expect(markup).not.toContain('href="/library/books/book%2Fid"');
  });

  it("keeps the UUID fallback display-only for unnamed Sessions", () => {
    const markup = renderDashboard({ status: "ready", items: [{
      ...recentItem,
      id: "7f0c9ea5-2c36-4a84-b55b-447e57c24736",
      name: "",
    }] });
    expect(markup).toContain("Unnamed Session c24736");
    expect(markup).toContain("/marginalia/sessions/7f0c9ea5-2c36-4a84-b55b-447e57c24736");
  });

  it("renders the authoritative order without deduplicating Sessions by Book", () => {
    const markup = renderDashboard({ status: "ready", items: [
      { ...recentItem, id: "session-2", name: "Newer pass" },
      { ...recentItem, id: "session-1", name: "Older pass" },
    ] });
    expect(markup.indexOf("Newer pass")).toBeLessThan(markup.indexOf("Older pass"));
    expect(markup.match(/href="\/marginalia\/sessions\//g)).toHaveLength(2);
  });

  it("renders the cover fallback when a recent Book has no cover", () => {
    const markup = renderDashboard({ status: "ready", items: [{
      ...recentItem,
      book: { ...recentItem.book, coverUrl: null },
    }] });
    expect(markup).toContain("No cover available for A Book");
  });

  it("renders the three launch pads with semantic action links and current destinations", () => {
    const all = renderDashboard({ status: "ready", items: [] });
    for (const title of ["My Marginalia", "My Shelves", "Browse Library"]) expect(all).toContain(title);
    for (const destination of [
      '/marginalia"', '/marginalia?view=books', '/marginalia/import', '/marginalia/export',
      '/shelves"', '/shelves/new', '/library"', '/library?view=authors', '/library?view=series', '/groups"',
    ]) expect(all).toContain(`href="${destination}`);
    expect(all).toContain('aria-label="My Marginalia actions"');
    expect(all).toContain('aria-hidden="true"');
    expect(all).toContain(">By Session</span>");
  });

  it("shows only enabled mode-aware and server-tool destinations", () => {
    const all = renderDashboard({ status: "ready", items: [] });
    for (const label of ["Groups", "Import Books", "Users", "Server Settings"]) expect(all).toContain(label);

    const reader = renderDashboard({ status: "ready", items: [] }, {
      showGroups: false,
      showImports: false,
      showUsers: false,
      showServerSettings: false,
    });
    for (const label of ["Groups", "Import Books", "Users", "Server Settings", "Server tools"]) expect(reader).not.toContain(label);
    for (const label of ["Books", "Authors", "Series", "By Session", "Import", "Export", "View Shelves", "Create Shelf"]) expect(reader).toContain(label);
  });

  it("calculates carousel end states and scrolls by a useful viewport increment", () => {
    expect(dashboardScrollerState({ scrollLeft: 0, clientWidth: 600, scrollWidth: 1000 })).toEqual({ hasOverflow: true, atStart: true, atEnd: false });
    expect(dashboardScrollerState({ scrollLeft: 400, clientWidth: 600, scrollWidth: 1000 })).toEqual({ hasOverflow: true, atStart: false, atEnd: true });
    expect(dashboardScrollerState({ scrollLeft: 0, clientWidth: 600, scrollWidth: 600 })).toEqual({ hasOverflow: false, atStart: true, atEnd: true });

    const scrollBy = vi.fn();
    scrollDashboardScroller({ clientWidth: 600, scrollBy }, 1);
    expect(scrollBy).toHaveBeenCalledWith({ left: 510, behavior: "smooth" });
    scrollDashboardScroller({ clientWidth: 600, scrollBy }, -1);
    expect(scrollBy).toHaveBeenLastCalledWith({ left: -510, behavior: "smooth" });
  });
});
