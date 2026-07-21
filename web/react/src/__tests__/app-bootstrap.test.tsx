import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { CurrentUser, ServerInfo } from "@second-pass/spl-api";
import { AppBootstrapView, forcedPasswordChangeDestination, type BootstrapState } from "../app/App";

const user: CurrentUser = { username: "owner", email: "owner@example.test", firstName: "Ada", lastName: "Reader", profileId: "profile-id", role: "manager", mustChangePassword: false, isOwner: true, advancedLibraryGroupsEnabled: false, canAccessDjangoAdmin: false, bannerText: "Maintenance tonight", groups: [] };
const server: ServerInfo = { name: "Family Library", description: "Books for everyone.", version: "0.1.0-dev", release: "Early Access", releaseDate: "2026-07-20", apiBaseUrl: "unused" };

function renderBootstrap(state: BootstrapState): string {
  return renderToStaticMarkup(<MemoryRouter><AppBootstrapView state={state} loginPath="/login/?next=%2Flibrary" onRetry={vi.fn()} onCurrentUserChange={vi.fn()} /></MemoryRouter>);
}

describe("app bootstrap", () => {
  it("renders loading state", () => { expect(renderBootstrap({ status: "loading" })).toContain('aria-busy="true"'); });
  it("renders user and server identity", () => {
    const markup = renderBootstrap({ status: "ready", user, server });
    expect(markup).toContain("Family Library");
    expect(markup).not.toContain("Books for everyone.");
    expect(markup).toContain('href="/logout/"');
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
