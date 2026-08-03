import { describe, expect, it } from "vitest";

import { listClientSessions, logoutCurrentWebSession, logoutOtherWebSessions, revokeClientSession } from "../accountSessions";
import type { ApiClient } from "../client";

describe("account sessions SDK", () => {
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
    await logoutCurrentWebSession(client);
    expect(calls).toEqual([
      { path: "/api/v1/accounts/me/client-sessions/", init: undefined },
      { path: "/api/v1/accounts/me/client-sessions/one/", init: { method: "DELETE" } },
      { path: "/api/v1/accounts/me/web-sessions/logout-others/", init: { method: "POST" } },
      { path: "/logout/", init: { method: "POST" } },
    ]);
  });
});
