import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { CurrentUser, ServerInfo } from "@second-pass/spl-api";
import { AppFrame } from "../app/layout/AppFrame";
import { ProfileOrchestrator } from "../features/profile/ProfileOrchestrator";

const user: CurrentUser = {
  username: "ada", email: "ada@example.test", firstName: "Ada", lastName: "Lovelace",
  profileId: "profile-id", role: "manager", mustChangePassword: false, isOwner: true,
  isManager: false, isLibrarian: false, isReader: false,
  advancedLibraryGroupsEnabled: false, canAccessDjangoAdmin: false, bannerText: "", groups: [],
};
const server: ServerInfo = { name: "Analytical Library", description: "", version: "0.1.0-dev", release: "Early Access", releaseDate: "2026-07-20", apiBaseUrl: "unused" };

describe("ProfileOrchestrator", () => {
  it("composes profile regions from app-owned current-user data", () => {
    const markup = renderToStaticMarkup(<MemoryRouter initialEntries={["/profile"]}><Routes><Route element={<AppFrame user={user} server={server} onCurrentUserChange={vi.fn()} />}><Route path="profile" element={<ProfileOrchestrator />} /></Route></Routes></MemoryRouter>);
    expect(markup).toContain("Ada Lovelace");
    expect(markup).toContain("ada@example.test");
    expect(markup).toContain("&lt;@ada&gt;");
    expect(markup).toContain("Owner");
    expect(markup).toContain('href="/profile/password"');
    expect(markup).toContain("Device/API sessions");
    expect(markup).not.toContain('<p class="eyebrow">Profile</p>');
  });
});
