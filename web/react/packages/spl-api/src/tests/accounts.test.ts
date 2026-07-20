import { describe, expect, it } from "vitest";

import { changeCurrentUserPassword, getCurrentUser, listClientSessions, logoutOtherWebSessions, revokeClientSession, updateCurrentUser } from "../accounts";
import type { ApiClient } from "../client";

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

  it("adapts safe self-profile updates to the server request shape", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    const response = {
      username: "reader", email: "new@example.test", first_name: "New", last_name: "Name",
      profile_id: "profile-id", role: "reader", must_change_password: false,
      is_owner: false, advanced_library_groups_enabled: false, banner_text: "", groups: [],
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

describe("account sessions", () => {
  it("maps connected-client metadata and session operations", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    const client: ApiClient = { request: async <T>(path: string, init?: RequestInit) => {
      calls.push({ path, init });
      if (path.endsWith("client-sessions/")) return [{ id: "one", name: "Phone", client_type: "reader", created_at: "created", updated_at: "updated", last_seen_at: null, revoked_at: null }] as T;
      return undefined as T;
    } };
    await expect(listClientSessions(client)).resolves.toEqual([{ id: "one", name: "Phone", clientType: "reader", createdAt: "created", updatedAt: "updated", lastSeenAt: undefined }]);
    await revokeClientSession("one", client);
    await logoutOtherWebSessions(client);
    expect(calls.map(({ path }) => path)).toEqual(["/api/v1/accounts/me/client-sessions/", "/api/v1/accounts/me/client-sessions/one/", "/api/v1/accounts/me/web-sessions/logout-others/"]);
  });
});
