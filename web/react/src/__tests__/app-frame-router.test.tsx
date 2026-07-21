import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { CurrentUser, ServerInfo } from "@second-pass/spl-api";
import { AppFrame } from "../app/layout/AppFrame";
import { appRoutes, NotFoundPageRegion, PlaceholderPageRegion, sectionRoutes } from "../app/router";
import { DashboardOrchestrator } from "../features/dashboard/DashboardOrchestrator";

const user: CurrentUser = { username: "owner", email: "", firstName: "", lastName: "", profileId: "profile", role: "manager", mustChangePassword: false, isOwner: true, advancedLibraryGroupsEnabled: false, bannerText: "", groups: [] };
const server: ServerInfo = { name: "Family Library", description: "Hidden", version: "0.1.0-dev", release: "Early Access", releaseDate: "2026-07-20", apiBaseUrl: "unused" };

describe("app frame and router", () => {
  it("renders the dashboard placeholder inside the frame", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><Routes><Route element={<AppFrame user={user} server={server} onCurrentUserChange={vi.fn()} />}><Route index element={<DashboardOrchestrator />} /></Route></Routes></MemoryRouter>);
    expect(markup).toContain("Your reading home");
    expect(markup).toContain("Dashboard preview");
    expect(markup).toContain("Family Library");
  });
  it("renders navigation with active state", () => {
    const markup = renderToStaticMarkup(<MemoryRouter initialEntries={["/library"]}><AppFrame user={user} server={server} onCurrentUserChange={vi.fn()} /></MemoryRouter>);
    for (const label of ["Dashboard", "My Marginalia", "Library", "Groups", "Shelves", "Import", "Users", "Server Settings"]) expect(markup).toContain(label);
    expect(markup).toMatch(/aria-current="page" class="active" href="\/library"/);
    expect(markup).toContain('href="/profile"');
  });
  it("defines placeholder and not-found routes", () => {
    expect(sectionRoutes.map(({ path }) => `/${path}`)).toEqual(["/reading", "/library", "/groups", "/shelves", "/imports", "/server"]);
    expect(appRoutes[0].children.some((route) => route.path === "users")).toBe(true);
    expect(appRoutes[0].children.some((route) => route.path === "users/:profileId/edit")).toBe(true);
    expect(renderToStaticMarkup(<PlaceholderPageRegion title="Library" />)).toContain("Library");
    expect(renderToStaticMarkup(<NotFoundPageRegion />)).toContain("Page not found");
  });
});
