/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CurrentUser, ServerInfo } from "@second-pass/spl-api";
import { AppOrchestrator, focusRouteHeading, navigationDestinationOwnsPath } from "../../src/app/layout/AppOrchestrator";
import { RouteModuleError, RouteModuleLoading } from "../../src/app/routing/RouteModuleBoundary";
import { buttonNamed } from "../support/domInteraction";

const user: CurrentUser = { username: "owner", email: "", firstName: "", lastName: "", profileId: "profile", role: "manager", mustChangePassword: false, isOwner: true, isManager: false, isLibrarian: false, isReader: false, canAccessDjangoAdmin: false, groups: [] };
const server: ServerInfo = { serverId: "server-id", serverUrls: [], name: "Family Library", description: "Hidden", bannerText: "", advancedLibraryGroupsEnabled: false, secondPassReaderWebClientUrl: null, marginaliaProfileUri: "profile", publicGroup: { id: "public", name: "Common Room", description: "" }, version: "0.1.0-dev", releaseDate: "2026-07-20" };
let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
});

function navMarkup(userOverrides: Partial<CurrentUser> = {}, serverOverrides: Partial<ServerInfo> = {}, path = "/library"): string {
  return renderToStaticMarkup(<MemoryRouter initialEntries={[path]}><AppOrchestrator user={{ ...user, ...userOverrides }} server={{ ...server, ...serverOverrides }} onCurrentUserChange={vi.fn()} /></MemoryRouter>);
}

describe("app frame and router", () => {
  it("provides a skip target and moves route focus to the page heading", () => {
    const markup = navMarkup();
    expect(markup).toContain('href="#main-content"');
    expect(markup).toContain('id="main-content"');
    expect(markup).toMatch(/<main\b[^>]*tabindex="-1"/);

    const main = document.createElement("main");
    main.innerHTML = "<h1>Library</h1>";
    document.body.append(main);
    expect(focusRouteHeading(main)).toBe(true);
    expect(document.activeElement).toBe(main.querySelector("h1"));
    expect(main.querySelector("h1")?.tabIndex).toBe(-1);
    main.remove();
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

  it.each([
    {
      label: "Owner in advanced mode",
      user: {},
      advanced: true,
      visible: ["/marginalia", "/library", "/groups", "/shelves", "/imports", "/users", "/server"],
      hidden: [],
    },
    {
      label: "Manager in simple mode",
      user: { isOwner: false, isManager: true },
      advanced: false,
      visible: ["/marginalia", "/library", "/shelves", "/imports", "/users"],
      hidden: ["/groups", "/server"],
    },
    {
      label: "Librarian in simple mode",
      user: { isOwner: false, isLibrarian: true },
      advanced: false,
      visible: ["/marginalia", "/library", "/shelves", "/imports"],
      hidden: ["/groups", "/users", "/server"],
    },
    {
      label: "Reader in advanced mode",
      user: { isOwner: false, isReader: true },
      advanced: true,
      visible: ["/marginalia", "/library", "/groups", "/shelves"],
      hidden: ["/imports", "/users", "/server"],
    },
  ])("shows the $label navigation contract", ({ user: facts, advanced, visible, hidden }) => {
    const markup = navMarkup(facts, { advancedLibraryGroupsEnabled: advanced });
    for (const path of visible) expect(markup).toContain(`href="${path}"`);
    for (const path of hidden) expect(markup).not.toContain(`href="${path}"`);
  });

  it("preserves accessible identity and account names for long crowded-header values", () => {
    const markup = navMarkup(
      { username: "owner-with-an-unusually-long-account-name" },
      { name: "The Exceptionally Long Household Library Name", advancedLibraryGroupsEnabled: true },
    );
    expect(markup).toContain('aria-label="Open Dashboard for The Exceptionally Long Household Library Name"');
    expect(markup).toContain('aria-label="Open account menu for owner-with-an-unusually-long-account-name"');
    for (const path of ["/marginalia", "/library", "/groups", "/shelves"]) {
      expect(markup).toContain(`href="${path}"`);
    }
  });

  it("uses the brand as the sole Dashboard link and marks it active at home", () => {
    const markup = navMarkup({}, {}, "/");

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
    expect(nestedLibrary).toMatch(/aria-current="page"[^>]*href="\/library"/);
    const profile = navMarkup({}, {}, "/profile/password");
    expect(profile).toContain("app-menu-component--active account-menu");
  });

  it("keeps route loading and lazy-module failures actionable", async () => {
    const container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);

    await act(async () => root?.render(<RouteModuleLoading />));
    expect(container.querySelector('[data-route-state="loading"]')?.getAttribute("aria-busy")).toBe("true");

    const reload = vi.fn();
    await act(async () => root?.render(<RouteModuleError onReload={reload} />));
    expect(container.querySelector('[data-route-state="error"] [role="alert"]')).not.toBeNull();
    await act(async () => buttonNamed(container, "Reload").click());
    expect(reload).toHaveBeenCalledOnce();
  });
});
