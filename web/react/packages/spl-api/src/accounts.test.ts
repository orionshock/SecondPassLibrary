import { describe, expect, it } from "vitest";

import { getCurrentUser } from "./accounts";
import type { ApiClient } from "./client";

describe("getCurrentUser", () => {
  it("maps the server bootstrap shape to a stable app-facing user", async () => {
    const response = {
      username: "reader",
      email: "reader@example.test",
      first_name: "Read",
      last_name: "Er",
      profile_id: "profile-id",
      role: "reader",
      must_change_password: false,
      is_owner: false,
      advanced_library_groups_enabled: true,
      banner_text: "Welcome",
      groups: [{ id: "group-id", name: "Public", is_public_group: true, is_curator: false }],
    };
    const client: ApiClient = {
      request: async <T>() => response as T,
    };

    await expect(getCurrentUser(client)).resolves.toEqual({
      username: "reader",
      email: "reader@example.test",
      firstName: "Read",
      lastName: "Er",
      profileId: "profile-id",
      role: "reader",
      mustChangePassword: false,
      isOwner: false,
      advancedLibraryGroupsEnabled: true,
      bannerText: "Welcome",
      groups: [{ id: "group-id", name: "Public", isPublicGroup: true, isCurator: false }],
    });
  });
});
