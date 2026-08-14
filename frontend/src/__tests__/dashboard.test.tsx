import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import type { RecentMarginaliaSession } from "@second-pass/spl-api";
import { DASHBOARD_RECENT_QUERY, DASHBOARD_RECENT_READING_LIMIT } from "../features/dashboard/DashboardOrchestrator";
import { dashboardScrollerState, scrollDashboardScroller } from "../features/dashboard/components/RecentSessionScroller";
import { DashboardPageRegion, type RecentReadingState } from "../features/dashboard/regions/DashboardPageRegion";

const recentItem: RecentMarginaliaSession = {
  id: "session-1",
  name: "Evening read",
  status: "active",
  lastActivityAt: "2026-07-27T18:30:00Z",
  progress: {
    cfi: "epubcfi(/6/8!/4/2)",
    locationLabel: "Chapter 08 · 42%",
    updatedAt: "2026-07-27T18:30:00Z",
  },
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
    bannerText="Maintenance tonight."
    recentReading={recentReading}
    showAdvancedGroups
    showImports
    showUsers
    showServerSettings
    onRetryRecentReading={vi.fn()}
    {...overrides}
  /></MemoryRouter>);
}

describe("Dashboard", () => {
  it("uses the canonical bounded active-only recent Marginalia request", () => {
    expect(DASHBOARD_RECENT_READING_LIMIT).toBe(50);
    expect(DASHBOARD_RECENT_QUERY).toEqual({ limit: 50 });
    expect(DASHBOARD_RECENT_QUERY).not.toHaveProperty("includeClosed");
  });

  it("uses the standard page title without an eyebrow or server description", () => {
    const markup = renderDashboard({ status: "loading" });
    expect(markup.match(/<h1>/g)).toHaveLength(1);
    expect(markup.match(/class="dashboard-banner"/g)).toHaveLength(1);
    expect(markup).not.toContain('class="eyebrow"');
    expect(markup).not.toContain('class="page-description"');
    expect(renderDashboard({ status: "loading" }, { bannerText: "  \n " })).not.toContain("dashboard-banner");
  });

  it("keeps recent-reading loading, empty, and failure states inside the section", () => {
    expect(renderDashboard({ status: "loading" })).toContain("Loading recent reading");
    const empty = renderDashboard({ status: "ready", items: [] });
    expect(empty).toContain("No recent reading activity yet.");
    expect(empty).toContain('href="/library"');
    expect(empty).not.toContain(">View all</a>");

    const failed = renderDashboard({ status: "error", error: new Error("Recent reading failed.") });
    expect(failed).toContain("Recent reading failed.");
    expect(failed).toContain("Retry");
    expect(failed).toContain("Maintenance tonight.");
    expect(failed).toContain("My Shelves");
    expect(failed).not.toContain(">View all</a>");
    expect(renderDashboard({ status: "loading" })).not.toContain(">View all</a>");
  });

  it("renders recent session facts and links to Session Detail", () => {
    const markup = renderDashboard({ status: "ready", items: [recentItem] });
    expect(markup).toContain("A Book");
    expect(markup).toContain("Evening read");
    expect(markup).toContain('dateTime="2026-07-27T18:30:00Z"');
    expect(markup).toContain('src="/media/cover.jpg"');
    expect(markup).toContain('href="/marginalia/sessions/session-1"');
    expect(markup).not.toContain('href="/library/books/book%2Fid"');
    expect(markup).toContain('href="/marginalia"');
    expect(markup).toContain(">View all</a>");
    expect(markup).toContain("Active");
    expect(markup).toContain("Chapter 08 · 42%");
    expect(markup).not.toContain('role="progressbar"');
    expect(markup).not.toContain("Open in Reader");
  });

  it("renders canonical closed Session status when supplied by the SDK boundary", () => {
    const markup = renderDashboard({ status: "ready", items: [{ ...recentItem, status: "closed" }] });
    expect(markup).toContain("Closed");
    expect(markup).toContain('href="/marginalia/sessions/session-1"');
  });

  it("omits progress cleanly when the Session has no saved location", () => {
    const markup = renderDashboard({ status: "ready", items: [{ ...recentItem, progress: null }] });

    expect(markup).not.toContain("dashboard-session-card__progress");
    expect(markup.match(/href="\/marginalia\/sessions\//g)).toHaveLength(1);
    expect(markup).not.toContain("dashboard-scroller__controls");
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

  it("bounds defensive presentation to the endpoint maximum", () => {
    const items = Array.from({ length: 52 }, (_, index) => ({
      ...recentItem,
      id: `session-${index}`,
      name: `Session ${index}`,
    }));
    const markup = renderDashboard({ status: "ready", items });

    expect(markup.match(/href="\/marginalia\/sessions\//g)).toHaveLength(50);
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
      '/shelves"', '/shelves?scope=shared', '/shelves?scope=group', '/shelves/new',
      '/library"', '/library?view=authors', '/library?view=series', '/groups"',
    ]) expect(all).toContain(`href="${destination}`);
    expect(all).toContain('aria-label="My Marginalia actions"');
    expect(all).toContain('aria-hidden="true"');
    expect(all).toContain(">By Session</span>");
  });

  it("uses authoritative Shelf scopes and adapts Shelf and Library grids to visible actions", () => {
    const advanced = renderDashboard({ status: "ready", items: [] });
    for (const link of [
      'href="/shelves"',
      'href="/shelves?scope=shared"',
      'href="/shelves?scope=group"',
      'href="/shelves/new"',
    ]) expect(advanced).toContain(link);
    expect(advanced.match(/data-action-count="4"/g)).toHaveLength(3);

    const simple = renderDashboard({ status: "ready", items: [] }, { showAdvancedGroups: false });
    expect(simple).toContain('href="/shelves?scope=group"');
    expect(simple).not.toContain('href="/groups"');
    expect(simple.match(/data-action-count="4"/g)).toHaveLength(2);
    expect(simple).toContain("dashboard-action-grid--count-4");
    expect(simple).not.toContain("dashboard-action-placeholder");
  });

  it("renders Server Tools in a detached secondary region with independent permission gates", () => {
    const all = renderDashboard({ status: "ready", items: [] });
    for (const label of ["Groups", "Import Books", "Users", "Server Settings"]) expect(all).toContain(label);
    expect(all).toContain('class="dashboard-server-tools"');
    expect(all.indexOf('class="dashboard-server-tools"')).toBeGreaterThan(all.indexOf('class="dashboard-launch-pads"'));

    const importsOnly = renderDashboard({ status: "ready", items: [] }, {
      showImports: true, showUsers: false, showServerSettings: false,
    });
    expect(importsOnly).toContain('href="/imports"');
    expect(importsOnly).not.toContain('href="/users"');
    expect(importsOnly).not.toContain('href="/server"');

    const reader = renderDashboard({ status: "ready", items: [] }, {
      showAdvancedGroups: false,
      showImports: false,
      showUsers: false,
      showServerSettings: false,
    });
    for (const label of ["Groups", "Import Books", "Users", "Server Settings", "Server tools"]) expect(reader).not.toContain(label);
    for (const label of ["Books", "Authors", "Series", "By Session", "Import", "Export", "My Shelves", "Shared with Me", "Group Shelves", "Create Shelf"]) expect(reader).toContain(label);
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
