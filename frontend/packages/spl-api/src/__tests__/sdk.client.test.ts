import { describe, expect, it, vi } from "vitest";

import { ApiError } from "../errors";
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

  it("downloads attachments with safe server or fallback filenames", async () => {
    const responses = [
      new Response("archive", { status: 200, headers: { "Content-Type": "application/json", "Content-Disposition": 'attachment; filename="marginalia.json"' } }),
      new Response("archive", { status: 200, headers: { "Content-Type": "application/octet-stream" } }),
    ];
    const fetchImplementation = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => responses.shift()!);
    const client = createApiClient(fetchImplementation, () => "csrf-token");

    const named = await client.requestAttachment("/export");
    const fallback = await client.requestAttachment("/export", { method: "POST" }, "fallback.json");

    expect(named).toMatchObject({ filename: "marginalia.json", contentType: "application/json" });
    expect(await named.blob.text()).toBe("archive");
    expect(fallback.filename).toBe("fallback.json");
    const [, postInit] = fetchImplementation.mock.calls[1];
    expect(postInit?.credentials).toBe("same-origin");
    expect(new Headers(postInit?.headers).get("X-CSRFToken")).toBe("csrf-token");
  });

  it("preserves structured JSON errors for attachment requests", async () => {
    const client = createApiClient(async () => new Response(
      JSON.stringify({ detail: "Select at least one session.", code: "INVALID_SELECTION", books: ["Required."] }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    ));

    await expect(client.requestAttachment("/export")).rejects.toEqual(
      new ApiError("Select at least one session.", 400, { code: "INVALID_SELECTION", fields: { books: ["Required."] } }),
    );
  });
});
