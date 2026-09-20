import { apiClient, type ApiClient } from "./client";

export interface GeneralServerSettings {
  serverId: string;
  name: string;
  description: string;
  bannerText: string;
  secondPassReaderWebClientUrl: string;
  secondPassReaderWebClientUrlLocked: boolean;
}

export interface PublicLibrarySettings {
  name: string;
  description: string;
}

export interface LibraryGroupsSettings {
  advancedGroupsEnabled: boolean;
}

export interface ServerSettings {
  general: GeneralServerSettings;
  publicLibrary: PublicLibrarySettings;
  libraryGroups: LibraryGroupsSettings;
}

export interface UpdateServerIdentityInput {
  name: string;
  description: string;
  bannerText: string;
}

export interface UpdatePublicLibrarySettingsInput {
  name: string;
  description: string;
}

interface ServerSettingsResponse {
  server_id: string;
  server_name: string;
  server_description: string;
  server_banner_message: string;
  public_group_name: string;
  public_group_description: string;
  advanced_library_groups_enabled: boolean;
  second_pass_reader_web_client_url: string;
  second_pass_reader_web_client_url_locked: boolean;
}

const settingsPath = "/api/v1/server/settings/";

export async function getServerSettings(client: ApiClient = apiClient): Promise<ServerSettings> {
  return mapServerSettings(await client.request<ServerSettingsResponse>(settingsPath));
}

export async function updateServerIdentity(
  input: UpdateServerIdentityInput,
  client: ApiClient = apiClient,
): Promise<ServerSettings> {
  return patchServerSettings({
    server_name: input.name.trim(),
    server_description: input.description.trim(),
    server_banner_message: input.bannerText.trim(),
  }, client);
}

export async function updateExternalServicesSettings(
  secondPassReaderWebClientUrl: string,
  client: ApiClient = apiClient,
): Promise<ServerSettings> {
  return patchServerSettings({
    second_pass_reader_web_client_url: secondPassReaderWebClientUrl.trim(),
  }, client);
}

export async function updatePublicLibrarySettings(
  input: UpdatePublicLibrarySettingsInput,
  client: ApiClient = apiClient,
): Promise<ServerSettings> {
  return patchServerSettings({
    public_group_name: input.name.trim(),
    public_group_description: input.description,
  }, client);
}

export async function enableAdvancedGroups(client: ApiClient = apiClient): Promise<ServerSettings> {
  const response = await client.request<ServerSettingsResponse>(
    "/api/v1/server/settings/advanced-library-groups/enable/",
    { method: "POST" },
  );
  return mapServerSettings(response);
}

async function patchServerSettings(body: Record<string, string>, client: ApiClient): Promise<ServerSettings> {
  const response = await client.request<ServerSettingsResponse>(settingsPath, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return mapServerSettings(response);
}

function mapServerSettings(response: ServerSettingsResponse): ServerSettings {
  return {
    general: {
      serverId: response.server_id,
      name: response.server_name,
      description: response.server_description,
      bannerText: response.server_banner_message,
      secondPassReaderWebClientUrl: response.second_pass_reader_web_client_url,
      secondPassReaderWebClientUrlLocked: response.second_pass_reader_web_client_url_locked,
    },
    publicLibrary: {
      name: response.public_group_name,
      description: response.public_group_description,
    },
    libraryGroups: {
      advancedGroupsEnabled: response.advanced_library_groups_enabled,
    },
  };
}
