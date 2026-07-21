import { describe, expect, it } from "vitest";

import { changeCurrentUserPassword, getCurrentUser, updateCurrentUser } from "../../packages/spl-api/src/accounts";
import type { ApiClient } from "../../packages/spl-api/src/client";

describe("getCurrentUser", () => {
  it("maps the server bootstrap shape to a stable app-facing user", async () => {
    const response = {
      username: "reader",
      email: "reader@example.test",
      first_name: "Read",
      last_name: "Er",
      profile_id: "profile-id",
      role: "reader",
      must_change_password: true,
      is_owner: true,
      advanced_library_groups_enabled: true,
      can_access_django_admin: true,
      banner_text: "Welcome",
      groups: [{ id: "group-id", name: "Public", is_public_group: true, is_curator: true }],
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
      mustChangePassword: true,
      isOwner: true,
      advancedLibraryGroupsEnabled: true,
      canAccessDjangoAdmin: true,
      bannerText: "Welcome",
      groups: [{ id: "group-id", name: "Public", isPublicGroup: true, isCurator: true }],
    });
  });

  it("normalizes omitted capability flags to stable false values", async () => {
    const response = {
      username: "reader", email: "", first_name: "", last_name: "",
      profile_id: "profile-id", role: "reader", banner_text: "",
      groups: [{ id: "group-id", name: "Public", is_public_group: true }],
    };
    const client: ApiClient = { request: async <T>() => response as T };

    const user = await getCurrentUser(client);

    expect(user.isOwner).toBe(false);
    expect(user.mustChangePassword).toBe(false);
    expect(user.advancedLibraryGroupsEnabled).toBe(false);
    expect(user.canAccessDjangoAdmin).toBe(false);
    expect(user.groups[0]?.isCurator).toBe(false);
  });

  it("adapts safe self-profile updates to the server request shape", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    const response = {
      username: "reader", email: "new@example.test", first_name: "New", last_name: "Name",
      profile_id: "profile-id", role: "reader", banner_text: "", groups: [],
    };
    const client: ApiClient = {
      request: async <T>(path: string, init?: RequestInit) => {
        calls.push({ path, init });
        return response as T;
      },
    };

    const user = await updateCurrentUser(
      { email: "new@example.test", firstName: "New", lastName: "Name" },
      client,
    );

    expect(calls[0]?.path).toBe("/api/v1/accounts/me/");
    expect(calls[0]?.init?.method).toBe("PATCH");
    expect(JSON.parse(String(calls[0]?.init?.body))).toEqual({
      email: "new@example.test", first_name: "New", last_name: "Name",
    });
    expect(user.firstName).toBe("New");
  });

  it("adapts self password changes to the server request shape", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    const client: ApiClient = {
      request: async <T>(path: string, init?: RequestInit) => {
        calls.push({ path, init });
        return { status: "ok" } as T;
      },
    };

    await changeCurrentUserPassword(
      { currentPassword: "old", newPassword: "new-password", confirmPassword: "new-password" },
      client,
    );

    expect(calls[0]?.path).toBe("/api/v1/accounts/me/change-password/");
    expect(calls[0]?.init?.method).toBe("POST");
    expect(JSON.parse(String(calls[0]?.init?.body))).toEqual({
      current_password: "old", new_password: "new-password", confirm_password: "new-password",
    });
  });
});
