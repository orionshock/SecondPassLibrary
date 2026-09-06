import { describe, expect, it } from "vitest";

import type { ApiClient } from "../../packages/spl-api/src/client";
import { decideClientPairing, lookupClientPairing } from "../../packages/spl-api/src/pairing";

describe("client pairing", () => {
  it("maps lookup results without exposing server response naming", async () => {
    const client: ApiClient = { request: async <T>() => ({ code: "ABCD-EFGH", client_name: "Reader", client_type: "reader", expires_at: "2026-01-01T00:00:00Z" }) as T };
    await expect(lookupClientPairing("abcd efgh", client)).resolves.toEqual({ code: "ABCD-EFGH", clientName: "Reader", clientType: "reader", expiresAt: "2026-01-01T00:00:00Z" });
  });

  it("sends an explicit approval decision", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    const client: ApiClient = { request: async <T>(path: string, init?: RequestInit) => { calls.push({ path, init }); return { status: "approved" } as T; } };
    await expect(decideClientPairing({ code: "ABCD-EFGH", action: "approve", clientName: "Phone" }, client)).resolves.toBe("approved");
    expect(calls[0]?.path).toBe("/api/v1/client-api/pairing/decision/");
    expect(JSON.parse(String(calls[0]?.init?.body))).toEqual({ code: "ABCD-EFGH", action: "approve", client_name: "Phone" });
  });
});
