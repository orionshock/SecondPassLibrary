import { apiClient, type ApiClient } from "./client";

interface ServerInfoResponse {
  server_name: string;
  server_description: string;
  server_version: string;
  server_release: string;
  server_release_date: string;
  api_base_url: string;
}

export interface ServerInfo {
  name: string;
  description: string;
  version: string;
  release: string;
  releaseDate: string;
  apiBaseUrl: string;
}

export async function getServerInfo(client: ApiClient = apiClient): Promise<ServerInfo> {
  const response = await client.request<ServerInfoResponse>("/.well-known/secondpass");
  return {
    name: response.server_name,
    description: response.server_description,
    version: response.server_version,
    release: response.server_release,
    releaseDate: response.server_release_date,
    apiBaseUrl: response.api_base_url,
  };
}
