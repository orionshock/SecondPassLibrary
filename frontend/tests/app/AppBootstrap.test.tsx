import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import type { CurrentUser, ServerInfo } from "@second-pass/spl-api";
import { AppBootstrapView, forcedPasswordChangeDestination, type BootstrapState } from "../../src/app/App";

const user: CurrentUser = { username: "owner", email: "owner@example.test", firstName: "Ada", lastName: "Reader", profileId: "profile-id", role: "manager", mustChangePassword: false, isOwner: true, isManager: false, isLibrarian: false, isReader: false, canAccessDjangoAdmin: false, groups: [] };
const server: ServerInfo = { name: "Family Library", description: "Books for everyone.", bannerText: "Maintenance tonight", advancedLibraryGroupsEnabled: false, secondPassReaderWebClientUrl: null, marginaliaProfileUri: "profile", publicGroup: { id: "public", name: "Common Room", description: "" }, version: "0.1.0-dev", releaseDate: "2026-07-20" };

function renderBootstrap(state: BootstrapState): string {
  return renderToStaticMarkup(<MemoryRouter><AppBootstrapView state={state} loginPath="/login/?next=%2Flibrary" onRetry={vi.fn()} onCurrentUserChange={vi.fn()} /></MemoryRouter>);
}

describe("app bootstrap", () => {
  it("renders loading state", () => { expect(renderBootstrap({ status: "loading" })).toContain('aria-busy="true"'); });
  it("renders user and server identity", () => {
    const markup = renderBootstrap({ status: "ready", user, server });
    expect(markup).toContain("Family Library");
    expect(markup).not.toContain("Books for everyone.");
    expect(markup).toContain('aria-label="Open account menu for owner"');
    expect(markup).not.toContain('href="/logout/"');
  });
  it("renders login for authentication failure", () => {
    const markup = renderBootstrap({ status: "failed", kind: "authentication" });
    expect(markup).toContain('href="/login/?next=%2Flibrary"');
    expect(markup).not.toContain("Retry");
  });
  it("renders retry for other failures", () => { expect(renderBootstrap({ status: "failed", kind: "network" })).toContain("Retry"); });
  it("forces password-change routing", () => {
    expect(forcedPasswordChangeDestination({ ...user, mustChangePassword: true }, "/profile")).toBe("/profile/password");
    expect(forcedPasswordChangeDestination({ ...user, mustChangePassword: true }, "/profile/password")).toBeUndefined();
  });
});

