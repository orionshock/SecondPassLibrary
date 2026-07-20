import { describe, expect, it } from "vitest";

import type { ApiClient } from "../../packages/spl-api/src/client";
import { getServerInfo } from "../../packages/spl-api/src/server";

describe("getServerInfo", () => {
  it("maps discovery metadata to a stable app-facing server identity", async () => {
    const response = {
      server_name: "Family Library",
      server_description: "Books for everyone.",
      server_version: "0.1.0-dev",
      server_release: "Early Access",
      server_release_date: "2026-07-20",
      api_base_url: "http://localhost:8000/api/v1/",
    };
    const client: ApiClient = { request: async <T>() => response as T };

    await expect(getServerInfo(client)).resolves.toEqual({
      name: "Family Library",
      description: "Books for everyone.",
      version: "0.1.0-dev",
      release: "Early Access",
      releaseDate: "2026-07-20",
      apiBaseUrl: "http://localhost:8000/api/v1/",
    });
  });
});
