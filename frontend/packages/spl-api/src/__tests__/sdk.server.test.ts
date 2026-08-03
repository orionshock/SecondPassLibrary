import { describe, expect, it } from "vitest";

import type { ApiClient } from "../client";
import { getServerDiscovery, getServerInfo } from "../server";

describe("server context", () => {
  it("maps authenticated server info", async () => {
    const calls: string[] = [];
    const response = {
      server_name: "Family Library",
      server_description: "Books for everyone.",
      server_banner_message: "Maintenance tonight.",
      advanced_library_groups_enabled: true,
      reading_client_base_url: "https://reader.example.com",
      marginalia_profile_uri: "https://secondpasslibrary.local/specs/marginalia/0.1.0",
      public_group: { id: "public-id", name: "Common Room", description: "Shared books." },
      server_version: "0.1.0-dev",
      server_release_date: "2026-07-20",
    };
    const client: ApiClient = { request: async <T>(path: string) => { calls.push(path); return response as T; } };

    await expect(getServerInfo(client)).resolves.toEqual({
      name: "Family Library",
      description: "Books for everyone.",
      bannerText: "Maintenance tonight.",
      advancedLibraryGroupsEnabled: true,
      readingClientBaseUrl: "https://reader.example.com",
      marginaliaProfileUri: "https://secondpasslibrary.local/specs/marginalia/0.1.0",
      publicGroup: { id: "public-id", name: "Common Room", description: "Shared books." },
      version: "0.1.0-dev",
      releaseDate: "2026-07-20",
    });
    expect(calls).toEqual(["/api/v1/server/info/"]);
  });

  it("keeps public discovery separate from authenticated context", async () => {
    const calls: string[] = [];
    const response = {
      server_name: "Family Library",
      server_description: "Books for everyone.",
      server_version: "0.1.0-dev",
      server_release_date: "2026-07-20",
      api_base_url: "http://localhost:8000/api/v1/",
    };
    const client: ApiClient = { request: async <T>(path: string) => { calls.push(path); return response as T; } };

    await expect(getServerDiscovery(client)).resolves.toEqual({
      name: "Family Library",
      description: "Books for everyone.",
      version: "0.1.0-dev",
      releaseDate: "2026-07-20",
      apiBaseUrl: "http://localhost:8000/api/v1/",
    });
    expect(calls).toEqual(["/.well-known/secondpass"]);
  });
});
