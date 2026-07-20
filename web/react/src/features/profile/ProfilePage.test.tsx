import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ApiError, type CurrentUser, type ServerInfo } from "@second-pass/spl-api";

import { AppFrame } from "../../app/layout/AppFrame";
import { DashboardPage } from "../dashboard/DashboardPage";
import { ProfilePage, ProfilePageView } from "./ProfilePage";

const user: CurrentUser = {
  username: "ada",
  email: "ada@example.test",
  firstName: "Ada",
  lastName: "Lovelace",
  profileId: "profile-id",
  role: "manager",
  mustChangePassword: true,
  isOwner: true,
  advancedLibraryGroupsEnabled: false,
  bannerText: "",
  groups: [],
};

const server: ServerInfo = {
  name: "Analytical Library",
  description: "",
  version: "0.1.0-dev",
  release: "Early Access",
  releaseDate: "2026-07-20",
  apiBaseUrl: "unused-in-ui-tests",
};

describe("first React feature pages", () => {
  it("renders the styled dashboard placeholder within the app frame", () => {
    const markup = renderToStaticMarkup(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route element={<AppFrame user={user} server={server} onCurrentUserChange={vi.fn()} />}>
            <Route index element={<DashboardPage />} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(markup).toContain("Your reading home");
    expect(markup).toContain("Dashboard preview");
    expect(markup).toContain("Analytical Library");
  });

  it("renders the Profile route from app-owned current-user data", () => {
    const markup = renderToStaticMarkup(
      <MemoryRouter initialEntries={["/profile"]}>
        <Routes>
          <Route element={<AppFrame user={user} server={server} onCurrentUserChange={vi.fn()} />}>
            <Route path="profile" element={<ProfilePage />} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(markup).toContain("Ada Lovelace");
    expect(markup).toContain("ada@example.test");
    expect(markup).toContain("Password change required");
    expect(markup).toContain("Save profile");
    expect(markup).toContain("Change password");
  });

  it("renders mutation success and field-error states", () => {
    const markup = renderToStaticMarkup(
      <ProfilePageView
        user={user}
        profileState={{ pending: false, message: "Profile saved." }}
        passwordState={{
          pending: false,
          error: new ApiError("Check the password.", 400, {
            fields: { current_password: ["Current password is incorrect."] },
          }),
        }}
        onSaveProfile={vi.fn()}
        onSavePassword={vi.fn()}
      />,
    );

    expect(markup).toContain("Profile saved.");
    expect(markup).toContain("Current password is incorrect.");
    expect(markup).toContain('role="alert"');
  });
});
