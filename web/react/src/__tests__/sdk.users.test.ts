import { describe, expect, it } from "vitest";

import {
  ApiError,
  addUserGroupMembership,
  createUser,
  getManagedUser,
  listAssignableGroupsForUser,
  listUsers,
  removeUserGroupMembership,
  resetManagedUserPassword,
  updateManagedUser,
  updateUserGroupCurator,
} from "@second-pass/spl-api";
import type { ApiClient } from "../../packages/spl-api/src/client";

describe("users SDK", () => {
  it("builds supported server query parameters and maps the paginated response", async () => {
    const calls: string[] = [];
    const response = {
      count: 1,
      next: "next-page",
      previous: null,
      results: [{
        profile_id: "profile-id",
        username: "owner",
        first_name: "Ada",
        last_name: "Lovelace",
        email: "ada@example.test",
        role: "manager",
        is_owner: true,
        is_active: false,
        date_joined: "2026-01-01T00:00:00Z",
        last_login: "2026-07-20T12:00:00Z",
        must_change_password: true,
        groups: [{ id: "group-id", name: "Curators", is_public_group: false, is_curator: true }],
      }],
    };
    const client: ApiClient = { request: async <T>(path: string) => { calls.push(path); return response as T; } };

    const page = await listUsers({ q: " Ada ", role: "owner", isActive: "false", ordering: "-name", page: 2, pageSize: 20 }, client);

    expect(calls).toEqual(["/api/v1/accounts/users/?q=Ada&role=owner&is_active=false&ordering=-name&page=2&page_size=20"]);
    expect(page).toEqual({
      count: 1,
      next: "next-page",
      previous: null,
      items: [{
        id: "profile-id",
        username: "owner",
        firstName: "Ada",
        lastName: "Lovelace",
        email: "ada@example.test",
        role: "manager",
        isOwner: true,
        isActive: false,
        dateJoined: "2026-01-01T00:00:00Z",
        lastLogin: "2026-07-20T12:00:00Z",
        mustChangePassword: true,
        groups: [{ id: "group-id", name: "Curators", isPublicGroup: false, isCurator: true }],
      }],
    });
  });

  it("preserves normalized SDK errors", async () => {
    const error = new Error("denied");
    const client: ApiClient = { request: async <T>() => Promise.reject(error) as Promise<T> };
    await expect(listUsers({}, client)).rejects.toBe(error);
  });

  it("creates an active-by-default user without sending activity and maps the one-time password", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    const response = {
      user: {
        profile_id: "new-id", username: "new-reader", first_name: "New", last_name: "Reader",
        email: "new@example.test", role: "reader", is_owner: false, is_active: true,
        date_joined: "2026-07-20T00:00:00Z", last_login: null, must_change_password: true, groups: [],
      },
      temporary_password: "temporary-secret",
      message: "Show this password now.",
    };
    const client: ApiClient = { request: async <T>(path: string, init?: RequestInit) => { calls.push({ path, init }); return response as T; } };

    const result = await createUser({ username: " new-reader ", email: " new@example.test ", firstName: " New ", lastName: " Reader ", role: "reader" }, client);

    expect(calls[0]?.path).toBe("/api/v1/accounts/users/");
    expect(calls[0]?.init?.method).toBe("POST");
    expect(JSON.parse(String(calls[0]?.init?.body))).toEqual({
      username: "new-reader", email: "new@example.test", first_name: "New", last_name: "Reader", role: "reader",
    });
    expect(JSON.parse(String(calls[0]?.init?.body))).not.toHaveProperty("is_active");
    expect(result.temporaryPassword).toBe("temporary-secret");
    expect(result.user).toMatchObject({ id: "new-id", isActive: true, mustChangePassword: true });
  });

  it("preserves create validation errors from the shared client boundary", async () => {
    const error = new ApiError("Invalid user.", 400, { fields: { username: ["Already exists."] } });
    const client: ApiClient = { request: async <T>() => Promise.reject(error) as Promise<T> };
    await expect(createUser({ username: "duplicate", email: "", firstName: "", lastName: "", role: "reader" }, client)).rejects.toBe(error);
  });

  it("maps managed detail and PATCH fields without leaking wire names", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    const response = {
      profile_id: "target-id", username: "reader", first_name: "Read", last_name: "Er", email: "reader@example.test",
      role: "reader", is_owner: false, is_active: false, date_joined: "2026-01-01T00:00:00Z", last_login: null,
      must_change_password: true, groups: [],
    };
    const client: ApiClient = { request: async <T>(path: string, init?: RequestInit) => { calls.push({ path, init }); return response as T; } };
    expect((await getManagedUser("target/id", client)).isActive).toBe(false);
    const updated = await updateManagedUser("target/id", { firstName: " New ", lastName: " Name ", email: " e@test ", role: "librarian", isActive: true, mustChangePassword: false }, client);
    expect(calls.map(({ path }) => path)).toEqual(["/api/v1/accounts/users/target%2Fid/", "/api/v1/accounts/users/target%2Fid/"]);
    expect(JSON.parse(String(calls[1]?.init?.body))).toEqual({ first_name: "New", last_name: "Name", email: "e@test", role: "librarian", is_active: true, must_change_password: false });
    expect(updated.mustChangePassword).toBe(true);
  });

  it("maps password reset without retaining the server copy block", async () => {
    const calls: string[] = [];
    const client: ApiClient = { request: async <T>(path: string) => { calls.push(path); return { username: "reader", temporary_password: "once", copy_block: "secret", message: "show once" } as T; } };
    await expect(resetManagedUserPassword("target", client)).resolves.toEqual({ username: "reader", temporaryPassword: "once", message: "show once" });
    expect(calls).toEqual(["/api/v1/accounts/users/target/reset-password/"]);
  });

  it("adapts group discovery and group-scoped membership mutations", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    const user = {
      profile_id: "target", username: "reader", first_name: "", last_name: "", email: "", role: "reader", is_owner: false,
      is_active: true, date_joined: "2026-01-01T00:00:00Z", last_login: null, must_change_password: false,
      groups: [{ id: "assigned", name: "Assigned", is_public_group: false, is_curator: false }],
    };
    const client: ApiClient = { request: async <T>(path: string, init?: RequestInit) => {
      calls.push({ path, init });
      if (path.includes("accounts/users")) return user as T;
      if (path.includes("?ordering")) return { count: 2, next: null, previous: null, results: [
        { id: "assigned", name: "Assigned", is_public_group: false },
        { id: "available", name: "Available", is_public_group: false },
      ] } as T;
      return undefined as T;
    } };
    await expect(listAssignableGroupsForUser("target", client)).resolves.toEqual([{ id: "available", name: "Available", isPublicGroup: false }]);
    await addUserGroupMembership("target", { groupId: "available", isCurator: true }, client);
    await updateUserGroupCurator("target", "available", false, client);
    await removeUserGroupMembership("target", "available", client);
    expect(JSON.parse(String(calls[2]?.init?.body))).toEqual({ user_id: "target", is_curator: true });
    expect(calls[3]).toMatchObject({ path: "/api/v1/library/groups/available/memberships/target/", init: { method: "PATCH" } });
    expect(calls[4]).toMatchObject({ path: "/api/v1/library/groups/available/memberships/target/", init: { method: "DELETE" } });
  });
});
