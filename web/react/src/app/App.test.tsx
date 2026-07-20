import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { CurrentUser, ServerInfo } from "@second-pass/spl-api";

import { AppBootstrapView, AppLayout, type BootstrapState } from "./App";
import { NotFoundPage, PlaceholderPage, sectionRoutes } from "./router";

const user: CurrentUser = {
  username: "owner",
  email: "owner@example.test",
  firstName: "Ada",
  lastName: "Reader",
  profileId: "profile-id",
  role: "manager",
  mustChangePassword: false,
  isOwner: true,
  advancedLibraryGroupsEnabled: false,
  bannerText: "Maintenance tonight",
  groups: [],
};

const server: ServerInfo = {
  name: "Family Library",
  description: "Books for everyone.",
  version: "0.1.0-dev",
  release: "Early Access",
  releaseDate: "2026-07-20",
  apiBaseUrl: "http://localhost:8000/api/v1/",
};

function renderBootstrap(state: BootstrapState): string {
  return renderToStaticMarkup(
    <MemoryRouter>
      <AppBootstrapView state={state} loginPath="/login/?next=%2Flibrary" onRetry={vi.fn()} />
    </MemoryRouter>,
  );
}

describe("app shell bootstrap", () => {
  it("renders a stable busy state while current-user loading is pending", () => {
    const markup = renderBootstrap({ status: "loading" });

    expect(markup).toContain('aria-busy="true"');
    expect(markup).toContain("Opening your library");
  });

  it("renders user and server identity after bootstrap succeeds", () => {
    const markup = renderBootstrap({ status: "ready", user, server });

    expect(markup).toContain("Family Library");
    expect(markup).toContain("Books for everyone.");
    expect(markup).toContain("Ada Reader");
    expect(markup).toContain("Maintenance tonight");
    expect(markup).toContain('href="/logout/"');
  });

  it("renders a login action for an authentication failure", () => {
    const markup = renderBootstrap({ status: "failed", kind: "authentication" });

    expect(markup).toContain("Log in");
    expect(markup).toContain('href="/login/?next=%2Flibrary"');
    expect(markup).not.toContain("Retry");
  });

  it("renders a retry action for a non-authentication failure", () => {
    const markup = renderBootstrap({ status: "failed", kind: "network" });

    expect(markup).toContain("Retry");
    expect(markup).not.toContain("Log in");
  });
});

describe("app shell navigation", () => {
  it("renders every section link and marks the current section active", () => {
    const markup = renderToStaticMarkup(
      <MemoryRouter initialEntries={["/library"]}>
        <AppLayout user={user} server={server} />
      </MemoryRouter>,
    );

    for (const label of [
      "Dashboard",
      "Library",
      "Groups",
      "Shelves",
      "Users",
      "Imports",
      "Server Settings",
    ]) {
      expect(markup).toContain(label);
    }
    expect(markup).toMatch(/aria-current="page" class="active" href="\/library"/);
  });

  it("defines the expected placeholder routes and an in-app not-found page", () => {
    expect(sectionRoutes.map(({ path }) => `/${path}`)).toEqual([
      "/library",
      "/groups",
      "/shelves",
      "/users",
      "/imports",
      "/server",
    ]);
    expect(renderToStaticMarkup(<PlaceholderPage title="Library" />)).toContain("Library");
    expect(renderToStaticMarkup(<NotFoundPage />)).toContain("Page not found");
  });
});
