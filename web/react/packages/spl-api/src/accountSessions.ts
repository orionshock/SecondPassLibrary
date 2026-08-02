import { apiClient, type ApiClient } from "./client";

interface ClientSessionResponse {
  id: string;
  name: string;
  client_type: string;
  created_at: string;
  updated_at: string;
  last_seen_at: string | null;
  revoked_at: string | null;
}

export interface ClientSession {
  id: string;
  name: string;
  clientType: string;
  createdAt: string;
  updatedAt: string;
  lastSeenAt?: string;
}

export async function logoutOtherWebSessions(client: ApiClient = apiClient): Promise<void> {
  await client.request<{ message: string }>("/api/v1/accounts/me/web-sessions/logout-others/", { method: "POST" });
}

export async function listClientSessions(client: ApiClient = apiClient): Promise<ClientSession[]> {
  const response = await client.request<ClientSessionResponse[]>("/api/v1/accounts/me/client-sessions/");
  return response.map(mapClientSession);
}

export async function revokeClientSession(sessionId: string, client: ApiClient = apiClient): Promise<void> {
  await client.request<void>(`/api/v1/accounts/me/client-sessions/${encodeURIComponent(sessionId)}/`, { method: "DELETE" });
}

function mapClientSession(response: ClientSessionResponse): ClientSession {
  return {
    id: response.id,
    name: response.name,
    clientType: response.client_type,
    createdAt: response.created_at,
    updatedAt: response.updated_at,
    lastSeenAt: response.last_seen_at ?? undefined,
  };
}
