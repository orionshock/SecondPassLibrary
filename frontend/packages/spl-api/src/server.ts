import { apiClient, type ApiClient } from "./client";

interface ServerInfoResponse {
  server_id: string;
  server_urls: string[];
  server_name: string;
  server_description: string;
  server_banner_message: string;
  advanced_library_groups_enabled: boolean;
  second_pass_reader_web_client_url: string | null;
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
  server_id: string;
  server_name: string;
  server_description: string;
  server_version: string;
  server_release_date: string;
}

export interface ServerInfo {
  serverId: string;
  serverUrls: string[];
  name: string;
  description: string;
  bannerText: string;
  advancedLibraryGroupsEnabled: boolean;
  secondPassReaderWebClientUrl: string | null;
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
  serverId: string;
  name: string;
  description: string;
  version: string;
  releaseDate: string;
}

export async function getServerInfo(client: ApiClient = apiClient): Promise<ServerInfo> {
  const response = await client.request<ServerInfoResponse>("/api/v1/server/info/");
  return {
    serverId: response.server_id,
    serverUrls: response.server_urls,
    name: response.server_name,
    description: response.server_description,
    bannerText: response.server_banner_message,
    advancedLibraryGroupsEnabled: response.advanced_library_groups_enabled,
    secondPassReaderWebClientUrl: response.second_pass_reader_web_client_url,
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
    serverId: response.server_id,
    name: response.server_name,
    description: response.server_description,
    version: response.server_version,
    releaseDate: response.server_release_date,
  };
}

export function libraryApiRoot(libraryBaseUrl: string): string {
  const base = libraryBaseUrl.trim();
  const parsed = new URL(base);
  if (
    !["http:", "https:"].includes(parsed.protocol)
    || parsed.username
    || parsed.password
    || parsed.pathname !== "/"
    || base.includes("?")
    || base.includes("#")
  ) {
    throw new TypeError("Library base URL must be an HTTP(S) origin.");
  }
  return `${base.replace(/\/$/, "")}/api/v1/`;
}
