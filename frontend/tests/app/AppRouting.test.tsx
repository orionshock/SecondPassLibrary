import { Children, isValidElement, type ReactElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";

import type { CurrentUser, ServerInfo } from "@second-pass/spl-api";
import { AppOrchestrator, navigationDestinationOwnsPath } from "../../src/app/layout/AppOrchestrator";
import { appRoutes, NotFoundPageRegion, PlaceholderPageRegion, sectionRoutes } from "../../src/app/router";
import {
  RouteModuleBoundary,
  RouteModuleError,
  RouteModuleLoading,
} from "../../src/app/routing/RouteModuleBoundary";
import { DashboardOrchestrator } from "../../src/features/dashboard/DashboardOrchestrator";

const user: CurrentUser = { username: "owner", email: "", firstName: "", lastName: "", profileId: "profile", role: "manager", mustChangePassword: false, isOwner: true, isManager: false, isLibrarian: false, isReader: false, canAccessDjangoAdmin: false, groups: [] };
const server: ServerInfo = { name: "Family Library", description: "Hidden", bannerText: "", advancedLibraryGroupsEnabled: false, secondPassReaderWebClientUrl: null, marginaliaProfileUri: "profile", publicGroup: { id: "public", name: "Common Room", description: "" }, version: "0.1.0-dev", releaseDate: "2026-07-20" };

function navMarkup(userOverrides: Partial<CurrentUser> = {}, serverOverrides: Partial<ServerInfo> = {}, path = "/library"): string {
  return renderToStaticMarkup(<MemoryRouter initialEntries={[path]}><AppOrchestrator user={{ ...user, ...userOverrides }} server={{ ...server, ...serverOverrides }} onCurrentUserChange={vi.fn()} /></MemoryRouter>);
}

describe("app frame and router", () => {
  it("renders the Dashboard inside the frame", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><Routes><Route element={<AppOrchestrator user={user} server={{ ...server, bannerText: "Maintenance tonight" }} onCurrentUserChange={vi.fn()} />}><Route index element={<DashboardOrchestrator />} /></Route></Routes></MemoryRouter>);
    expect(markup).toContain('class="app-shell"');
    expect(markup).toContain('class="product-page-shell dashboard-page"');
    expect(markup).toContain('class="dashboard-banner"');
    expect(markup).toContain('aria-busy="true"');
    expect(markup).not.toContain('class="eyebrow"');
    expect(markup).not.toContain('class="page-description"');
  });

  it("keeps Dashboard banner content out of the global frame on other routes", () => {
    const markup = navMarkup({}, { bannerText: "Dashboard only notice" });
    expect(markup).not.toContain("Dashboard only notice");
    expect(markup).toContain('href="/library"');
    expect(markup).toContain('aria-label="Open Dashboard for Family Library"');
    expect(markup).toContain('aria-label="Open account menu for owner"');
    expect(markup).not.toContain("@owner");
    expect(markup).not.toContain('>Dashboard</span>');
    expect(markup).not.toContain('href="/profile"');
  });
  it("shows every navigation branch to an Owner when advanced groups are enabled", () => {
    const markup = navMarkup({}, { advancedLibraryGroupsEnabled: true });
    expect(markup).toContain('class="app-header app-header--full-navigation"');
    for (const path of ["/marginalia", "/library", "/groups", "/shelves", "/imports", "/users", "/server"]) {
      expect(markup.match(new RegExp(`href="${path}"`, "g"))).toHaveLength(1);
    }
    expect(markup).toContain("Book Import");
    expect(markup).not.toContain(">Dashboard<");
    expect(markup).toMatch(/class="app-navigation-link app-navigation-link--primary active"[^>]*href="\/library"/);
    expect(markup).toContain('aria-label="More navigation"');
    expect(markup).toContain('aria-label="Open account menu for owner"');
  });

  it("preserves accessible identity and account names for long crowded-header values", () => {
    const markup = navMarkup(
      { username: "owner-with-an-unusually-long-account-name" },
      { name: "The Exceptionally Long Household Library Name", advancedLibraryGroupsEnabled: true },
    );
    expect(markup).toContain('class="app-header app-header--full-navigation"');
    expect(markup).toContain('aria-label="Open Dashboard for The Exceptionally Long Household Library Name"');
    expect(markup).toContain('aria-label="Open account menu for owner-with-an-unusually-long-account-name"');
    for (const path of ["/marginalia", "/library", "/groups", "/shelves"]) {
      expect(markup).toContain(`href="${path}"`);
    }
  });

  it("shows Manager navigation without Server Settings and gates Groups by mode", () => {
    const manager = { isOwner: false, isManager: true };
    const simpleMarkup = navMarkup(manager);
    expect(simpleMarkup).toContain('href="/imports"');
    expect(simpleMarkup).toContain('href="/users"');
    expect(simpleMarkup).not.toContain('href="/server"');
    expect(simpleMarkup).not.toContain('href="/groups"');
    expect(simpleMarkup).not.toContain("app-header--full-navigation");
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
    for (const path of ["/marginalia", "/library", "/shelves"]) expect(markup).toContain(`href="${path}"`);
    for (const path of ["/groups", "/imports", "/users", "/server"]) expect(markup).not.toContain(`href="${path}"`);
    expect(navMarkup(reader, { advancedLibraryGroupsEnabled: true })).toContain('href="/groups"');
  });

  it("uses the brand as the sole Dashboard link and marks it active at home", () => {
    const markup = navMarkup({}, {}, "/");

    expect(markup).toMatch(/class="app-identity active"[^>]*href="\/"/);
    expect(markup).toContain('aria-current="page"');
    expect((markup.match(/href="\/"/g) ?? [])).toHaveLength(1);
    expect(markup).not.toContain(">Dashboard<");
  });

  it("matches nested routes to their owning destination without prefix collisions", () => {
    for (const [destination, path] of [
      ["/marginalia", "/marginalia/sessions/session-id"],
      ["/library", "/library/books/book-id/edit"],
      ["/shelves", "/shelves/shelf-id/edit"],
      ["/imports", "/imports"],
      ["/server", "/server"],
      ["/profile", "/profile/password"],
    ]) expect(navigationDestinationOwnsPath(destination, path)).toBe(true);
    expect(navigationDestinationOwnsPath("/library", "/libraryish")).toBe(false);

    const nestedLibrary = navMarkup({}, {}, "/library/books/book-id/edit");
    expect(nestedLibrary).toMatch(/app-navigation-link--primary active[^>]*href="\/library"/);
    const profile = navMarkup({}, {}, "/profile/password");
    expect(profile).toContain("app-menu-component--active account-menu");
  });

  it("hides Groups in simple mode for every role", () => {
    for (const facts of [
      { isOwner: true },
      { isOwner: false, isManager: true },
      { isOwner: false, isLibrarian: true },
      { isOwner: false, isReader: true },
    ]) expect(navMarkup(facts, { advancedLibraryGroupsEnabled: false })).not.toContain('href="/groups"');
  });
  it("keeps Dashboard eager and defines implemented Product routes separately from placeholders", () => {
    expect(sectionRoutes.map(({ path }) => `/${path}`)).toEqual([]);
    const dashboardRoute = appRoutes[0].children.find((route) => "index" in route && route.index);
    expect(isValidElement(dashboardRoute?.element)).toBe(true);
    if (isValidElement(dashboardRoute?.element)) expect(dashboardRoute.element.type).toBe(DashboardOrchestrator);
    const marginaliaRoute = appRoutes[0].children.find((route) => route.path === "marginalia");
    expect(isValidElement(marginaliaRoute?.element)).toBe(true);
    const marginaliaImportRoute = appRoutes[0].children.find((route) => route.path === "marginalia/import");
    expect(isValidElement(marginaliaImportRoute?.element)).toBe(true);
    const marginaliaExportRoute = appRoutes[0].children.find((route) => route.path === "marginalia/export");
    expect(isValidElement(marginaliaExportRoute?.element)).toBe(true);
    expect(appRoutes[0].children.some((route) => route.path?.startsWith("reading"))).toBe(false);
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

  it("resolves coherent feature and rare-route modules", async () => {
    const [library, libraryMutation, marginalia, marginaliaTransfer, shelves, groups, groupManagement, administration, profile] = await Promise.all([
      import("../../src/app/routes/libraryRoutes"),
      import("../../src/app/routes/libraryMutationRoutes"),
      import("../../src/app/routes/marginaliaRoutes"),
      import("../../src/app/routes/marginaliaTransferRoutes"),
      import("../../src/app/routes/shelvesRoutes"),
      import("../../src/app/routes/groupsRoutes"),
      import("../../src/app/routes/groupManagementRoutes"),
      import("../../src/app/routes/administrationRoutes"),
      import("../../src/app/routes/profileRoutes"),
    ]);
    for (const routeComponent of [
      library.LibraryOrchestrator,
      library.BookDetailOrchestrator,
      libraryMutation.BookEditOrchestrator,
      libraryMutation.AuthorSeriesEditOrchestrator,
      marginalia.MarginaliaSessionsOrchestrator,
      marginalia.MarginaliaSessionDetailOrchestrator,
      marginaliaTransfer.MarginaliaImportOrchestrator,
      marginaliaTransfer.MarginaliaExportOrchestrator,
      shelves.ShelvesListOrchestrator,
      shelves.ShelfEditOrchestrator,
      groups.GroupsListOrchestrator,
      groups.GroupDetailOrchestrator,
      groupManagement.GroupCreateOrchestrator,
      groupManagement.GroupEditOrchestrator,
      administration.ImportsOrchestrator,
      administration.UsersListOrchestrator,
      administration.ServerSettingsOrchestrator,
      profile.ProfileOrchestrator,
      profile.PasswordChangeOrchestrator,
    ]) expect(typeof routeComponent).toBe("function");
  });

  it("keeps route loading and lazy-module failures bounded inside the shell", () => {
    expect(renderToStaticMarkup(<RouteModuleLoading />)).toContain('data-route-state="loading"');
    const reload = vi.fn();
    const error = RouteModuleError({ onReload: reload }) as ReactElement<{ children: ReactNode }>;
    expect(renderToStaticMarkup(error)).toContain('data-route-state="error"');
    const reloadButton = Children.toArray(error.props.children)[1] as ReactElement<{ onClick: () => void }>;
    reloadButton.props.onClick();
    expect(reload).toHaveBeenCalledOnce();
    expect(RouteModuleBoundary.getDerivedStateFromError()).toEqual({ failed: true });
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

