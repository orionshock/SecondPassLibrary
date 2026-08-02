import { apiClient, type ApiClient } from "./client";

interface ServerInfoResponse {
  server_name: string;
  server_description: string;
  server_banner_message: string;
  advanced_library_groups_enabled: boolean;
  reading_client_base_url: string | null;
  marginalia_profile_uri: string;
  public_group: {
    id: string;
    name: string;
    description: string;
  };
  server_version: string;
  server_release_date: string;
}

interface ServerDiscoveryResponse {
  server_name: string;
  server_description: string;
  server_version: string;
  server_release_date: string;
  api_base_url: string;
}

export interface ServerInfo {
  name: string;
  description: string;
  bannerText: string;
  advancedLibraryGroupsEnabled: boolean;
  readingClientBaseUrl: string | null;
  marginaliaProfileUri: string;
  publicGroup: {
    id: string;
    name: string;
    description: string;
  };
  version: string;
  releaseDate: string;
}

export interface ServerDiscovery {
  name: string;
  description: string;
  version: string;
  releaseDate: string;
  apiBaseUrl: string;
}

export async function getServerInfo(client: ApiClient = apiClient): Promise<ServerInfo> {
  const response = await client.request<ServerInfoResponse>("/api/v1/server/info/");
  return {
    name: response.server_name,
    description: response.server_description,
    bannerText: response.server_banner_message,
    advancedLibraryGroupsEnabled: response.advanced_library_groups_enabled,
    readingClientBaseUrl: response.reading_client_base_url,
    marginaliaProfileUri: response.marginalia_profile_uri,
    publicGroup: {
      id: response.public_group.id,
      name: response.public_group.name,
      description: response.public_group.description,
    },
    version: response.server_version,
    releaseDate: response.server_release_date,
  };
}

export async function getServerDiscovery(client: ApiClient = apiClient): Promise<ServerDiscovery> {
  const response = await client.request<ServerDiscoveryResponse>("/.well-known/secondpass");
  return {
    name: response.server_name,
    description: response.server_description,
    version: response.server_version,
    releaseDate: response.server_release_date,
    apiBaseUrl: response.api_base_url,
  };
}
