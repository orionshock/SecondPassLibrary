import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ApiError, type CurrentUser, type ServerInfo } from "@second-pass/spl-api";

import { AppFrame } from "../../app/layout/AppFrame";
import { DashboardPage } from "../dashboard/DashboardPage";
import {
  ProfilePage,
  ProfilePageView,
  passwordDraftReducer,
  profileDraftFromUser,
  profileDraftReducer,
} from "./ProfilePage";

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

  it("renders stable success check icons for both mutations", () => {
    const markup = renderToStaticMarkup(
      <ProfilePageView
        user={user}
        profileState={{ pending: false, message: "Profile saved." }}
        passwordState={{ pending: false, message: "Password changed." }}
        onSaveProfile={vi.fn()}
        onSavePassword={vi.fn()}
        onCancelProfile={vi.fn()}
        onCancelPassword={vi.fn()}
      />,
    );

    expect(markup).toContain("Profile saved.");
    expect(markup).toContain("Password changed.");
    expect(markup.match(/check_circle/g)).toHaveLength(2);
    expect(markup).toContain("success-icon");
  });

  it("renders profile and password errors beside their action areas", () => {
    const markup = renderToStaticMarkup(
      <ProfilePageView
        user={user}
        profileState={{
          pending: false,
          error: new ApiError("Check the profile.", 400, {
            fields: { email: ["Enter a valid email address."] },
          }),
        }}
        passwordState={{
          pending: false,
          error: new ApiError("Check the password.", 400, {
            fields: { current_password: ["Current password is incorrect."] },
          }),
        }}
        onSaveProfile={vi.fn()}
        onSavePassword={vi.fn()}
        onCancelProfile={vi.fn()}
        onCancelPassword={vi.fn()}
      />,
    );

    expect(markup).toContain("Enter a valid email address.");
    expect(markup).toContain("Current password is incorrect.");
    expect(markup).toContain('role="alert"');
    expect(markup.match(/form-action-row/g)).toHaveLength(2);
  });

  it("resets unsaved profile edits to current user values", () => {
    const saved = profileDraftFromUser(user);
    const edited = profileDraftReducer(saved, {
      type: "change",
      field: "email",
      value: "unsaved@example.test",
    });

    expect(profileDraftReducer(edited, { type: "reset", value: saved })).toEqual(saved);
  });

  it("clears every unsaved password field", () => {
    const edited = {
      currentPassword: "not-logged",
      newPassword: "not-logged-either",
      confirmPassword: "still-not-logged",
    };

    expect(passwordDraftReducer(edited, { type: "reset" })).toEqual({
      currentPassword: "",
      newPassword: "",
      confirmPassword: "",
    });
  });
});
