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
