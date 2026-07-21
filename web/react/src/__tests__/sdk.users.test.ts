import { describe, expect, it } from "vitest";

import { listUsers } from "@second-pass/spl-api";
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
});
