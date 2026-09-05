import { describe, expect, it } from "vitest";

import { ApiError, enableAdvancedGroups, getServerSettings, updateExternalServicesSettings, updatePublicLibrarySettings, updateServerIdentity } from "@second-pass/spl-api";
import type { ApiClient } from "../client";

const response = {
  server_name: "Virgo SPL",
  server_description: "Private library",
  server_banner_message: "Maintenance tonight",
  public_group_name: "Common Room",
  public_group_description: "Shared books",
  advanced_library_groups_enabled: false,
  second_pass_reader_web_client_url: "https://reader.example.com",
  second_pass_reader_web_client_url_locked: false,
};

describe("server settings SDK", () => {
  it("maps the Owner settings response into stable sections", async () => {
    const calls: string[] = [];
    const client: ApiClient = { request: async <T>(path: string) => { calls.push(path); return response as T; } };
    await expect(getServerSettings(client)).resolves.toEqual({
      general: { name: "Virgo SPL", description: "Private library", bannerText: "Maintenance tonight", secondPassReaderWebClientUrl: "https://reader.example.com", secondPassReaderWebClientUrlLocked: false },
      publicLibrary: { name: "Common Room", description: "Shared books" },
      libraryGroups: { advancedGroupsEnabled: false },
    });
    expect(calls).toEqual(["/api/v1/server/settings/"]);
  });

  it("sends section-specific PATCH bodies", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    const client: ApiClient = { request: async <T>(path: string, init?: RequestInit) => { calls.push({ path, init }); return response as T; } };
    await updateServerIdentity({ name: " New name ", description: " <p>Desc</p> ", bannerText: " <strong>Banner</strong> " }, client);
    await updateExternalServicesSettings(" https://reader.example.com/ ", client);
    await updatePublicLibrarySettings({ name: " Public ", description: " Shared " }, client);
    expect(JSON.parse(String(calls[0]?.init?.body))).toEqual({ server_name: "New name", server_description: "<p>Desc</p>", server_banner_message: "<strong>Banner</strong>" });
    expect(JSON.parse(String(calls[1]?.init?.body))).toEqual({ second_pass_reader_web_client_url: "https://reader.example.com/" });
    expect(JSON.parse(String(calls[2]?.init?.body))).toEqual({ public_group_name: "Public", public_group_description: " Shared " });
    expect(calls.every(({ init }) => init?.method === "PATCH")).toBe(true);
  });

  it("uses the one-way enable endpoint and maps enabled state", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    const client: ApiClient = { request: async <T>(path: string, init?: RequestInit) => { calls.push({ path, init }); return { ...response, advanced_library_groups_enabled: true } as T; } };
    await expect(enableAdvancedGroups(client)).resolves.toMatchObject({ libraryGroups: { advancedGroupsEnabled: true } });
    expect(calls).toEqual([{ path: "/api/v1/server/settings/advanced-library-groups/enable/", init: { method: "POST" } }]);
  });

  it("preserves permission and validation errors from the shared client", async () => {
    const forbidden = new ApiError("Not allowed.", 403);
    const invalid = new ApiError("Invalid.", 400, { fields: { server_name: ["Required."] } });
    const forbiddenClient: ApiClient = { request: async <T>() => Promise.reject(forbidden) as Promise<T> };
    const invalidClient: ApiClient = { request: async <T>() => Promise.reject(invalid) as Promise<T> };
    await expect(getServerSettings(forbiddenClient)).rejects.toBe(forbidden);
    await expect(updateServerIdentity({ name: "", description: "", bannerText: "" }, invalidClient)).rejects.toBe(invalid);
  });
});
