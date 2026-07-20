import { apiClient, type ApiClient } from "./client";

interface CurrentUserResponse {
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  profile_id: string;
  role: string;
  must_change_password: boolean;
  is_owner: boolean;
  advanced_library_groups_enabled: boolean;
  banner_text: string;
  groups: Array<{
    id: string;
    name: string;
    is_public_group: boolean;
    is_curator: boolean;
  }>;
}

export interface CurrentUser {
  username: string;
  email: string;
  firstName: string;
  lastName: string;
  profileId: string;
  role: string;
  mustChangePassword: boolean;
  isOwner: boolean;
  advancedLibraryGroupsEnabled: boolean;
  bannerText: string;
  groups: Array<{
    id: string;
    name: string;
    isPublicGroup: boolean;
    isCurator: boolean;
  }>;
}

export interface UpdateCurrentUserInput {
  email: string;
  firstName: string;
  lastName: string;
}

export interface ChangeCurrentUserPasswordInput {
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
}

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

export async function getCurrentUser(client: ApiClient = apiClient): Promise<CurrentUser> {
  const response = await client.request<CurrentUserResponse>("/api/v1/accounts/me/");
  return mapCurrentUser(response);
}

export async function updateCurrentUser(
  input: UpdateCurrentUserInput,
  client: ApiClient = apiClient,
): Promise<CurrentUser> {
  const response = await client.request<CurrentUserResponse>("/api/v1/accounts/me/", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: input.email,
      first_name: input.firstName,
      last_name: input.lastName,
    }),
  });
  return mapCurrentUser(response);
}

export async function changeCurrentUserPassword(
  input: ChangeCurrentUserPasswordInput,
  client: ApiClient = apiClient,
): Promise<void> {
  await client.request<{ status: string }>("/api/v1/accounts/me/change-password/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      current_password: input.currentPassword,
      new_password: input.newPassword,
      confirm_password: input.confirmPassword,
    }),
  });
}

export async function logoutOtherWebSessions(client: ApiClient = apiClient): Promise<void> {
  await client.request<{ message: string }>("/api/v1/accounts/me/web-sessions/logout-others/", {
    method: "POST",
  });
}

export async function listClientSessions(client: ApiClient = apiClient): Promise<ClientSession[]> {
  const response = await client.request<ClientSessionResponse[]>("/api/v1/accounts/me/client-sessions/");
  return response.map(mapClientSession);
}

export async function revokeClientSession(
  sessionId: string,
  client: ApiClient = apiClient,
): Promise<void> {
  await client.request<void>(`/api/v1/accounts/me/client-sessions/${encodeURIComponent(sessionId)}/`, {
    method: "DELETE",
  });
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

function mapCurrentUser(response: CurrentUserResponse): CurrentUser {
  return {
    username: response.username,
    email: response.email,
    firstName: response.first_name,
    lastName: response.last_name,
    profileId: response.profile_id,
    role: response.role,
    mustChangePassword: response.must_change_password,
    isOwner: response.is_owner,
    advancedLibraryGroupsEnabled: response.advanced_library_groups_enabled,
    bannerText: response.banner_text,
    groups: response.groups.map((group) => ({
      id: group.id,
      name: group.name,
      isPublicGroup: group.is_public_group,
      isCurator: group.is_curator,
    })),
  };
}
