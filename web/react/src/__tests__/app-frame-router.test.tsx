import { isValidElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { CurrentUser, ServerInfo } from "@second-pass/spl-api";
import { AppFrame } from "../app/layout/AppFrame";
import { appRoutes, NotFoundPageRegion, PlaceholderPageRegion, sectionRoutes } from "../app/router";
import { DashboardOrchestrator } from "../features/dashboard/DashboardOrchestrator";
import { ReadingSessionsOrchestrator } from "../features/reading/ReadingSessionsOrchestrator";
import { ReadingExportOrchestrator } from "../features/reading/ReadingExportOrchestrator";
import { ReadingImportOrchestrator } from "../features/reading/ReadingImportOrchestrator";

const user: CurrentUser = { username: "owner", email: "", firstName: "", lastName: "", profileId: "profile", role: "manager", mustChangePassword: false, isOwner: true, isManager: false, isLibrarian: false, isReader: false, canAccessDjangoAdmin: false, groups: [] };
const server: ServerInfo = { name: "Family Library", description: "Hidden", bannerText: "", advancedLibraryGroupsEnabled: false, publicGroup: { id: "public", name: "Common Room", description: "" }, version: "0.1.0-dev", releaseDate: "2026-07-20" };

function navMarkup(userOverrides: Partial<CurrentUser> = {}, serverOverrides: Partial<ServerInfo> = {}): string {
  return renderToStaticMarkup(<MemoryRouter initialEntries={["/library"]}><AppFrame user={{ ...user, ...userOverrides }} server={{ ...server, ...serverOverrides }} onCurrentUserChange={vi.fn()} /></MemoryRouter>);
}

describe("app frame and router", () => {
  it("renders the Dashboard inside the frame", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><Routes><Route element={<AppFrame user={user} server={{ ...server, bannerText: "Maintenance tonight" }} onCurrentUserChange={vi.fn()} />}><Route index element={<DashboardOrchestrator />} /></Route></Routes></MemoryRouter>);
    expect(markup).toContain("Your reading home");
    expect(markup).toContain("Recent active reading");
    expect(markup).toContain("Loading recent reading");
    expect(markup).toContain("Maintenance tonight");
    expect(markup).toContain("Family Library");
  });

  it("keeps Dashboard banner content out of the global frame on other routes", () => {
    const markup = navMarkup({}, { bannerText: "Dashboard only notice" });
    expect(markup).not.toContain("Dashboard only notice");
    expect(markup).toContain('href="/library"');
    expect(markup).toContain('href="/profile"');
    expect(markup).toContain('aria-label="User owner"');
    expect(markup).not.toContain("@owner");
    expect(markup).toContain('href="/logout/"');
  });
  it("shows every navigation branch to an Owner when advanced groups are enabled", () => {
    const markup = navMarkup({}, { advancedLibraryGroupsEnabled: true });
    for (const path of ["/reading", "/library", "/groups", "/shelves", "/imports", "/users", "/server", "/profile", "/logout/"]) expect(markup).toContain(`href="${path}"`);
    expect(markup).toMatch(/aria-current="page" class="active" href="\/library"/);
  });

  it("shows Manager navigation without Server Settings and gates Groups by mode", () => {
    const manager = { isOwner: false, isManager: true };
    const simpleMarkup = navMarkup(manager);
    expect(simpleMarkup).toContain('href="/imports"');
    expect(simpleMarkup).toContain('href="/users"');
    expect(simpleMarkup).not.toContain('href="/server"');
    expect(simpleMarkup).not.toContain('href="/groups"');
    expect(navMarkup(manager, { advancedLibraryGroupsEnabled: true })).toContain('href="/groups"');
  });

  it("shows Imports but not Users or Server Settings to Librarians", () => {
    const markup = navMarkup({ isOwner: false, isLibrarian: true });
    expect(markup).toContain('href="/imports"');
    expect(markup).not.toContain('href="/users"');
    expect(markup).not.toContain('href="/server"');
  });

  it("shows only general branches to Readers and allows Groups only in advanced mode", () => {
    const reader = { isOwner: false, isReader: true };
    const markup = navMarkup(reader);
    for (const path of ["/reading", "/library", "/shelves", "/profile", "/logout/"]) expect(markup).toContain(`href="${path}"`);
    for (const path of ["/groups", "/imports", "/users", "/server"]) expect(markup).not.toContain(`href="${path}"`);
    expect(navMarkup(reader, { advancedLibraryGroupsEnabled: true })).toContain('href="/groups"');
  });

  it("hides Groups in simple mode for every role", () => {
    for (const facts of [
      { isOwner: true },
      { isOwner: false, isManager: true },
      { isOwner: false, isLibrarian: true },
      { isOwner: false, isReader: true },
    ]) expect(navMarkup(facts, { advancedLibraryGroupsEnabled: false })).not.toContain('href="/groups"');
  });
  it("defines implemented Product routes separately from placeholders", () => {
    expect(sectionRoutes.map(({ path }) => `/${path}`)).toEqual([]);
    const readingRoute = appRoutes[0].children.find((route) => route.path === "reading");
    expect(isValidElement(readingRoute?.element)).toBe(true);
    if (isValidElement(readingRoute?.element)) expect(readingRoute.element.type).toBe(ReadingSessionsOrchestrator);
    const readingImportRoute = appRoutes[0].children.find((route) => route.path === "reading/import");
    expect(isValidElement(readingImportRoute?.element)).toBe(true);
    if (isValidElement(readingImportRoute?.element)) expect(readingImportRoute.element.type).toBe(ReadingImportOrchestrator);
    const readingExportRoute = appRoutes[0].children.find((route) => route.path === "reading/export");
    expect(isValidElement(readingExportRoute?.element)).toBe(true);
    if (isValidElement(readingExportRoute?.element)) expect(readingExportRoute.element.type).toBe(ReadingExportOrchestrator);
    expect(appRoutes[0].children.some((route) => route.path === "groups")).toBe(true);
    expect(appRoutes[0].children.some((route) => route.path === "groups/new")).toBe(true);
    expect(appRoutes[0].children.some((route) => route.path === "groups/:groupId/edit")).toBe(true);
    expect(appRoutes[0].children.some((route) => route.path === "groups/:groupId")).toBe(true);
    expect(appRoutes[0].children.some((route) => route.path === "shelves")).toBe(true);
    expect(appRoutes[0].children.some((route) => route.path === "shelves/new")).toBe(true);
    expect(appRoutes[0].children.some((route) => route.path === "shelves/:shelfId/edit")).toBe(true);
    expect(appRoutes[0].children.some((route) => route.path === "shelves/:shelfId")).toBe(true);
    expect(appRoutes[0].children.some((route) => route.path === "library")).toBe(true);
    expect(appRoutes[0].children.some((route) => route.path === "library/books/:bookId")).toBe(true);
    expect(appRoutes[0].children.some((route) => route.path === "library/books/:bookId/edit")).toBe(true);
    for (const path of [
      "library/authors/new",
      "library/authors/:authorId/edit",
      "library/series/new",
      "library/series/:seriesId/edit",
    ]) expect(appRoutes[0].children.some((route) => route.path === path)).toBe(true);
    expect(appRoutes[0].children.some((route) => route.path === "imports")).toBe(true);
    expect(appRoutes[0].children.some((route) => route.path === "users")).toBe(true);
    expect(appRoutes[0].children.some((route) => route.path === "users/new")).toBe(true);
    expect(appRoutes[0].children.some((route) => route.path === "users/:profileId/edit")).toBe(true);
    expect(appRoutes[0].children.some((route) => route.path === "server")).toBe(true);
    expect(renderToStaticMarkup(<PlaceholderPageRegion title="Future section" />)).toContain("Future section");
    expect(renderToStaticMarkup(<NotFoundPageRegion />)).toContain("Page not found");
  });

  it("guards Groups routes by the server-driven advanced-groups mode, not role rank", () => {
    for (const path of ["groups", "groups/:groupId", "groups/:groupId/edit"]) {
      const route = appRoutes[0].children.find((candidate) => candidate.path === path);
      expect(isValidElement<{ canAccess: (candidate: CurrentUser, context: ServerInfo) => boolean }>(route?.element)).toBe(true);
      if (!isValidElement<{ canAccess: (candidate: CurrentUser, context: ServerInfo) => boolean }>(route?.element)) continue;
      expect(route.element.props.canAccess({ ...user, isOwner: false, isReader: true }, { ...server, advancedLibraryGroupsEnabled: true })).toBe(true);
      expect(route.element.props.canAccess({ ...user, isOwner: true }, { ...server, advancedLibraryGroupsEnabled: false })).toBe(false);
    }
  });

  it("guards Group creation by advanced mode and Manager authority", () => {
    const route = appRoutes[0].children.find((candidate) => candidate.path === "groups/new");
    expect(isValidElement<{ canAccess: (candidate: CurrentUser, context: ServerInfo) => boolean }>(route?.element)).toBe(true);
    if (!isValidElement<{ canAccess: (candidate: CurrentUser, context: ServerInfo) => boolean }>(route?.element)) return;
    expect(route.element.props.canAccess({ ...user, isOwner: false, isManager: true }, { ...server, advancedLibraryGroupsEnabled: true })).toBe(true);
    expect(route.element.props.canAccess({ ...user, isOwner: false, isLibrarian: true }, { ...server, advancedLibraryGroupsEnabled: true })).toBe(false);
    expect(route.element.props.canAccess({ ...user, isOwner: true }, { ...server, advancedLibraryGroupsEnabled: false })).toBe(false);
  });

  it("guards direct Book Edit access with the Librarian-level role contract", () => {
    const route = appRoutes[0].children.find((candidate) => candidate.path === "library/books/:bookId/edit");
    expect(isValidElement<{ canAccess: (candidate: CurrentUser) => boolean }>(route?.element)).toBe(true);
    if (!isValidElement<{ canAccess: (candidate: CurrentUser) => boolean }>(route?.element)) return;
    expect(route.element.props.canAccess({ ...user, isOwner: false, isReader: true })).toBe(false);
    expect(route.element.props.canAccess({ ...user, isOwner: false, isLibrarian: true })).toBe(true);
  });

  it("guards Author and Series lifecycle routes with the Librarian-level role contract", () => {
    const paths = [
      "library/authors/new",
      "library/authors/:authorId/edit",
      "library/series/new",
      "library/series/:seriesId/edit",
    ];
    for (const path of paths) {
      const route = appRoutes[0].children.find((candidate) => candidate.path === path);
      expect(isValidElement<{ canAccess: (candidate: CurrentUser) => boolean }>(route?.element)).toBe(true);
      if (!isValidElement<{ canAccess: (candidate: CurrentUser) => boolean }>(route?.element)) continue;
      expect(route.element.props.canAccess({ ...user, isOwner: false, isReader: true })).toBe(false);
      expect(route.element.props.canAccess({ ...user, isOwner: false, isLibrarian: true })).toBe(true);
    }
  });
});
