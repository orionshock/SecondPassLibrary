import { describe, expect, it } from "vitest";

import type { ApiClient } from "../../packages/spl-api/src/client";
import { getServerDiscovery, getServerInfo, libraryApiRoot } from "../../packages/spl-api/src/server";

describe("server context", () => {
  it("maps authenticated server info", async () => {
    const calls: string[] = [];
    const response = {
      server_id: "0f7262f1-d0b8-49fc-bb18-e40e46f56af2",
      server_urls: ["https://library.home.example", "https://library.tailnet.example", "https://library.public.example"],
      server_name: "Family Library",
      server_description: "Books for everyone.",
      server_banner_message: "Maintenance tonight.",
      advanced_library_groups_enabled: true,
      second_pass_reader_web_client_url: "https://reader.example.com",
      marginalia_profile_uri: "https://secondpasslibrary.local/specs/marginalia/0.1.0",
      public_group: { id: "public-id", name: "Common Room", description: "Shared books." },
      server_version: "0.1.0-dev",
      server_release_date: "2026-07-20",
    };
    const client: ApiClient = { request: async <T>(path: string) => { calls.push(path); return response as T; } };

    await expect(getServerInfo(client)).resolves.toEqual({
      serverId: "0f7262f1-d0b8-49fc-bb18-e40e46f56af2",
      serverUrls: ["https://library.home.example", "https://library.tailnet.example", "https://library.public.example"],
      name: "Family Library",
      description: "Books for everyone.",
      bannerText: "Maintenance tonight.",
      advancedLibraryGroupsEnabled: true,
      secondPassReaderWebClientUrl: "https://reader.example.com",
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
      server_id: "0f7262f1-d0b8-49fc-bb18-e40e46f56af2",
      server_name: "Family Library",
      server_description: "Books for everyone.",
      server_version: "0.1.0-dev",
      server_release_date: "2026-07-20",
    };
    const client: ApiClient = { request: async <T>(path: string) => { calls.push(path); return response as T; } };

    await expect(getServerDiscovery(client)).resolves.toEqual({
      serverId: "0f7262f1-d0b8-49fc-bb18-e40e46f56af2",
      name: "Family Library",
      description: "Books for everyone.",
      version: "0.1.0-dev",
      releaseDate: "2026-07-20",
    });
    expect(calls).toEqual(["/.well-known/secondpass"]);
  });

  it("derives the fixed API root from a Library base URL", () => {
    expect(libraryApiRoot(" https://library.example.com:8443/ ")).toBe("https://library.example.com:8443/api/v1/");
    expect(libraryApiRoot("http://192.168.1.25:8000")).toBe("http://192.168.1.25:8000/api/v1/");
    expect(() => libraryApiRoot("https://library.example.com/books")).toThrow(TypeError);
    expect(() => libraryApiRoot("https://library.example.com/?view=books")).toThrow(TypeError);
  });
});
