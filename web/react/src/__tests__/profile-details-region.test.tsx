import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { ApiError, type CurrentUser } from "@second-pass/spl-api";
import { ProfileDetailsPageRegion, profileDraftFromUser, profileDraftReducer } from "../features/profile/regions/ProfileDetailsPageRegion";

const user: CurrentUser = { username: "ada", email: "ada@example.test", firstName: "Ada", lastName: "Lovelace", profileId: "profile", role: "manager", mustChangePassword: false, isOwner: true, advancedLibraryGroupsEnabled: false, canAccessDjangoAdmin: false, bannerText: "", groups: [] };

describe("ProfileDetailsPageRegion", () => {
  it("renders success feedback without duplicating identity fields", () => {
    const markup = renderToStaticMarkup(<ProfileDetailsPageRegion user={user} state={{ pending: false, message: "Profile saved." }} onSave={vi.fn()} onClearStatus={vi.fn()} />);
    expect(markup).toContain("Profile saved.");
    expect(markup).toContain("check_circle");
    expect(markup).not.toContain("Profile details");
  });

  it("renders field errors in edit mode", () => {
    const markup = renderToStaticMarkup(<ProfileDetailsPageRegion user={user} state={{ pending: false, error: new ApiError("Check profile", 400, { fields: { email: ["Enter a valid email address."] } }) }} onSave={vi.fn()} onClearStatus={vi.fn()} />);
    expect(markup).toContain("Enter a valid email address.");
    expect(markup).toContain('role="alert"');
    expect(markup).toContain("Save profile");
  });

  it("resets unsaved profile edits", () => {
    const saved = profileDraftFromUser(user);
    const edited = profileDraftReducer(saved, { type: "change", field: "email", value: "unsaved@example.test" });
    expect(profileDraftReducer(edited, { type: "reset", value: saved })).toEqual(saved);
  });
});
