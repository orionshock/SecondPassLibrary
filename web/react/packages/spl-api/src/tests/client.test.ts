import { describe, expect, it, vi } from "vitest";

import { createApiClient } from "../client";

describe("createApiClient", () => {
  it("adds same-origin credentials and CSRF to unsafe requests", async () => {
    const fetchImplementation = vi.fn(
      async (_input: RequestInfo | URL, _init?: RequestInit): Promise<Response> => new Response(
        JSON.stringify({ status: "ok" }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    const client = createApiClient(fetchImplementation, () => "csrf-token");

    await client.request("/server-owned-path", { method: "POST" });

    const [, init] = fetchImplementation.mock.calls[0];
    expect(init?.credentials).toBe("same-origin");
    expect(new Headers(init?.headers).get("X-CSRFToken")).toBe("csrf-token");
  });
});
