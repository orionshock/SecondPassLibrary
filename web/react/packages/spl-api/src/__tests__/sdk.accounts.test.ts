import { describe, expect, it } from "vitest";

import {
  canSeeImports,
  canSeeServerSettings,
  canSeeUsers,
  changeCurrentUserPassword,
  getCurrentUser,
  isAtLeastLibrarian,
  isAtLeastManager,
  updateCurrentUser,
  type CurrentUserRoleFacts,
} from "../accounts";
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
      isManager: false,
      isLibrarian: false,
      isReader: false,
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
    expect(user.isManager).toBe(false);
    expect(user.isLibrarian).toBe(false);
    expect(user.isReader).toBe(true);
    expect(user.mustChangePassword).toBe(false);
    expect(user.advancedLibraryGroupsEnabled).toBe(false);
    expect(user.canAccessDjangoAdmin).toBe(false);
    expect(user.groups[0]?.isCurator).toBe(false);
  });

  it("maps each non-Owner role to one stable role fact without new wire fields", async () => {
    for (const role of ["manager", "librarian", "reader"] as const) {
      const response = {
        username: role, email: "", first_name: "", last_name: "",
        profile_id: `${role}-id`, role, banner_text: "", groups: [],
      };
      const client: ApiClient = { request: async <T>() => response as T };

      const user = await getCurrentUser(client);

      expect([user.isManager, user.isLibrarian, user.isReader]).toEqual([
        role === "manager", role === "librarian", role === "reader",
      ]);
    }
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

describe("current-user role helpers", () => {
  const roles: Record<string, CurrentUserRoleFacts> = {
    owner: { isOwner: true, isManager: false, isLibrarian: false, isReader: false },
    manager: { isOwner: false, isManager: true, isLibrarian: false, isReader: false },
    librarian: { isOwner: false, isManager: false, isLibrarian: true, isReader: false },
    reader: { isOwner: false, isManager: false, isLibrarian: false, isReader: true },
  };

  it("derives presentation visibility from stable role facts", () => {
    expect(Object.fromEntries(Object.entries(roles).map(([name, user]) => [name, {
      librarian: isAtLeastLibrarian(user),
      manager: isAtLeastManager(user),
      imports: canSeeImports(user),
      users: canSeeUsers(user),
      server: canSeeServerSettings(user),
    }]))).toEqual({
      owner: { librarian: true, manager: true, imports: true, users: true, server: true },
      manager: { librarian: true, manager: true, imports: true, users: true, server: false },
      librarian: { librarian: true, manager: false, imports: true, users: false, server: false },
      reader: { librarian: false, manager: false, imports: false, users: false, server: false },
    });
  });
});
