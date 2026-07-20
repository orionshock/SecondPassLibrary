import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ApiError, type CurrentUser, type ServerInfo } from "@second-pass/spl-api";

import { AppFrame } from "../../app/layout/AppFrame";
import { DashboardPage } from "../dashboard/DashboardPage";
import {
  confirmClientSessionRevoke,
  ProfilePage,
  ProfilePageView,
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
    expect(markup).toMatch(/<dt>Role<\/dt><dd><span[^>]*>Owner<\/span><\/dd>/);
    expect(markup).not.toContain("<dt>Owner</dt>");
    expect(markup).toContain("Save profile");
    expect(markup).toContain("Change password");
    expect(markup).toContain('href="/profile/password"');
  });

  it("renders a stable success check icon for profile updates", () => {
    const markup = renderToStaticMarkup(
      <MemoryRouter><ProfilePageView
        user={user}
        profileState={{ pending: false, message: "Profile saved." }}
        onSaveProfile={vi.fn()}
        onCancelProfile={vi.fn()}
      /></MemoryRouter>,
    );

    expect(markup).toContain("Profile saved.");
    expect(markup.match(/check_circle/g)).toHaveLength(1);
    expect(markup).toContain("success-icon");
  });

  it("renders profile errors beside the action area", () => {
    const markup = renderToStaticMarkup(
      <MemoryRouter><ProfilePageView
        user={user}
        profileState={{
          pending: false,
          error: new ApiError("Check the profile.", 400, {
            fields: { email: ["Enter a valid email address."] },
          }),
        }}
        onSaveProfile={vi.fn()}
        onCancelProfile={vi.fn()}
      /></MemoryRouter>,
    );

    expect(markup).toContain("Enter a valid email address.");
    expect(markup).toContain('role="alert"');
    expect(markup.match(/form-action-row/g)).toHaveLength(1);
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

  it("requires browser confirmation before revoking a connected client", () => {
    const confirm = vi.fn(() => false);
    expect(confirmClientSessionRevoke("Living Room Reader", confirm)).toBe(false);
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining("Living Room Reader"));
  });

});
