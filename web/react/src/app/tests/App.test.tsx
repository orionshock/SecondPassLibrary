import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { CurrentUser, ServerInfo } from "@second-pass/spl-api";

import { AppBootstrapView, forcedPasswordChangeDestination, type BootstrapState } from "../App";
import { AppFrame } from "../layout/AppFrame";
import { NotFoundPage, PlaceholderPage, sectionRoutes } from "../router";

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
  apiBaseUrl: "unused-in-ui-tests",
};

function renderBootstrap(state: BootstrapState): string {
  return renderToStaticMarkup(
    <MemoryRouter>
      <AppBootstrapView
        state={state}
        loginPath="/login/?next=%2Flibrary"
        onRetry={vi.fn()}
        onCurrentUserChange={vi.fn()}
      />
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
    expect(markup).not.toContain("Books for everyone.");
    expect(markup).toContain('href="/profile"');
    expect(markup).toContain(">owner</a>");
    expect(markup).toContain("Maintenance tonight");
    expect(markup).toContain('href="/logout/"');
    expect(markup).toContain("Second Pass Library");
    expect(markup).toContain("0.1.0-dev");
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
  it("forces password-change users away from every other React route", () => {
    expect(forcedPasswordChangeDestination({ ...user, mustChangePassword: true }, "/profile")).toBe("/profile/password");
    expect(forcedPasswordChangeDestination({ ...user, mustChangePassword: true }, "/profile/password")).toBeUndefined();
  });
  it("renders every section link and marks the current section active", () => {
    const markup = renderToStaticMarkup(
      <MemoryRouter initialEntries={["/library"]}>
        <AppFrame user={user} server={server} onCurrentUserChange={vi.fn()} />
      </MemoryRouter>,
    );

    for (const label of [
      "Dashboard",
      "My Marginalia",
      "Library",
      "Groups",
      "Shelves",
      "Import",
      "Server Settings",
    ]) {
      expect(markup).toContain(label);
    }
    expect(markup).toMatch(/aria-current="page" class="active" href="\/library"/);
    expect(markup).toContain('<a class="profile-link" href="/profile"');
    expect(markup).not.toContain("Books for everyone.");
  });

  it("defines the expected placeholder routes and an in-app not-found page", () => {
    expect(sectionRoutes.map(({ path }) => `/${path}`)).toEqual([
      "/reading",
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
