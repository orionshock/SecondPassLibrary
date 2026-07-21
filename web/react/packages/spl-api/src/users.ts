import { apiClient, type ApiClient } from "./client";
import { toPage, type ApiPage, type Page } from "./pagination";

export type UserRoleFilter = "owner" | "manager" | "librarian" | "reader" | "curator";
export type CreateUserRole = "manager" | "librarian" | "reader";
export type ManagedUserRole = CreateUserRole;
export type UserStatusFilter = "true" | "false";
export type UserOrdering =
  | "username" | "-username"
  | "name" | "-name"
  | "role" | "-role"
  | "is_active" | "-is_active";

export interface UsersListQuery {
  q?: string;
  role?: UserRoleFilter;
  isActive?: UserStatusFilter;
  ordering?: UserOrdering;
  page?: number;
  pageSize?: number;
}

export interface ManagedUserGroup {
  id: string;
  name: string;
  isPublicGroup: boolean;
  isCurator: boolean;
}

export interface ManagedUser {
  id: string;
  username: string;
  firstName: string;
  lastName: string;
  email: string;
  role: string;
  isOwner: boolean;
  isActive: boolean;
  dateJoined: string;
  lastLogin: string | null;
  mustChangePassword: boolean;
  groups: ManagedUserGroup[];
}

export interface CreateUserInput {
  username: string;
  email: string;
  firstName: string;
  lastName: string;
  role: CreateUserRole;
}

export interface CreateUserResult {
  user: ManagedUser;
  temporaryPassword: string;
  message: string;
}

export interface UpdateManagedUserInput {
  email?: string;
  firstName?: string;
  lastName?: string;
  role?: ManagedUserRole;
  isActive?: boolean;
  mustChangePassword?: boolean;
}

export interface ManagedPasswordResetResult {
  username: string;
  temporaryPassword: string;
  message: string;
}

export interface AssignableGroup {
  id: string;
  name: string;
  isPublicGroup: boolean;
}

export interface AddUserGroupMembershipInput {
  groupId: string;
  isCurator: boolean;
}

interface ManagedUserResponse {
  profile_id: string;
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  role: string;
  is_owner: boolean;
  is_active: boolean;
  date_joined: string;
  last_login: string | null;
  must_change_password: boolean;
  groups: Array<{
    id: string;
    name: string;
    is_public_group: boolean;
    is_curator: boolean;
  }>;
}

interface CreateUserResponse {
  user: ManagedUserResponse;
  temporary_password: string;
  message: string;
}

interface ManagedPasswordResetResponse {
  username: string;
  temporary_password: string;
  message: string;
}

interface LibraryGroupResponse {
  id: string;
  name: string;
  is_public_group: boolean;
}

export async function listUsers(query: UsersListQuery = {}, client: ApiClient = apiClient): Promise<Page<ManagedUser>> {
  const parameters = new URLSearchParams();
  const search = query.q?.trim();
  if (search) parameters.set("q", search);
  if (query.role) parameters.set("role", query.role);
  if (query.isActive) parameters.set("is_active", query.isActive);
  if (query.ordering) parameters.set("ordering", query.ordering);
  if (query.page) parameters.set("page", String(query.page));
  if (query.pageSize) parameters.set("page_size", String(query.pageSize));
  const queryString = parameters.toString();
  const response = await client.request<ApiPage<ManagedUserResponse>>(
    `/api/v1/accounts/users/${queryString ? `?${queryString}` : ""}`,
  );
  return toPage(response, mapManagedUser);
}

export async function createUser(input: CreateUserInput, client: ApiClient = apiClient): Promise<CreateUserResult> {
  const response = await client.request<CreateUserResponse>("/api/v1/accounts/users/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      username: input.username.trim(),
      email: input.email.trim(),
      first_name: input.firstName.trim(),
      last_name: input.lastName.trim(),
      role: input.role,
    }),
  });
  return {
    user: mapManagedUser(response.user),
    temporaryPassword: response.temporary_password,
    message: response.message,
  };
}

export async function getManagedUser(profileId: string, client: ApiClient = apiClient): Promise<ManagedUser> {
  return mapManagedUser(await client.request<ManagedUserResponse>(managedUserPath(profileId)));
}

export async function updateManagedUser(
  profileId: string,
  input: UpdateManagedUserInput,
  client: ApiClient = apiClient,
): Promise<ManagedUser> {
  const body: Record<string, string | boolean> = {};
  if (input.email !== undefined) body.email = input.email.trim();
  if (input.firstName !== undefined) body.first_name = input.firstName.trim();
  if (input.lastName !== undefined) body.last_name = input.lastName.trim();
  if (input.role !== undefined) body.role = input.role;
  if (input.isActive !== undefined) body.is_active = input.isActive;
  if (input.mustChangePassword !== undefined) body.must_change_password = input.mustChangePassword;
  const response = await client.request<ManagedUserResponse>(managedUserPath(profileId), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return mapManagedUser(response);
}

export async function resetManagedUserPassword(
  profileId: string,
  client: ApiClient = apiClient,
): Promise<ManagedPasswordResetResult> {
  const response = await client.request<ManagedPasswordResetResponse>(`${managedUserPath(profileId)}reset-password/`, {
    method: "POST",
  });
  return { username: response.username, temporaryPassword: response.temporary_password, message: response.message };
}

export async function listAssignableGroupsForUser(
  profileId: string,
  client: ApiClient = apiClient,
): Promise<AssignableGroup[]> {
  const user = await getManagedUser(profileId, client);
  const assigned = new Set(user.groups.map(({ id }) => id));
  const groups: LibraryGroupResponse[] = [];
  let path: string | null = "/api/v1/library/groups/?ordering=name&page_size=100";
  while (path) {
    const page: ApiPage<LibraryGroupResponse> = await client.request<ApiPage<LibraryGroupResponse>>(path);
    groups.push(...page.results);
    path = page.next;
  }
  return groups
    .filter(({ id }) => !assigned.has(id))
    .map((group) => ({ id: group.id, name: group.name, isPublicGroup: group.is_public_group }));
}

export async function addUserGroupMembership(
  profileId: string,
  input: AddUserGroupMembershipInput,
  client: ApiClient = apiClient,
): Promise<void> {
  await client.request(`/api/v1/library/groups/${encodeURIComponent(input.groupId)}/memberships/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: profileId, is_curator: input.isCurator }),
  });
}

export async function removeUserGroupMembership(
  profileId: string,
  groupId: string,
  client: ApiClient = apiClient,
): Promise<void> {
  await client.request(`${membershipPath(groupId, profileId)}`, { method: "DELETE" });
}

export async function updateUserGroupCurator(
  profileId: string,
  groupId: string,
  isCurator: boolean,
  client: ApiClient = apiClient,
): Promise<void> {
  await client.request(`${membershipPath(groupId, profileId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_curator: isCurator }),
  });
}

function managedUserPath(profileId: string): string {
  return `/api/v1/accounts/users/${encodeURIComponent(profileId)}/`;
}

function membershipPath(groupId: string, profileId: string): string {
  return `/api/v1/library/groups/${encodeURIComponent(groupId)}/memberships/${encodeURIComponent(profileId)}/`;
}

export function mapManagedUser(response: ManagedUserResponse): ManagedUser {
  return {
    id: response.profile_id,
    username: response.username,
    firstName: response.first_name,
    lastName: response.last_name,
    email: response.email,
    role: response.role,
    isOwner: response.is_owner,
    isActive: response.is_active,
    dateJoined: response.date_joined,
    lastLogin: response.last_login,
    mustChangePassword: response.must_change_password,
    groups: response.groups.map((group) => ({
      id: group.id,
      name: group.name,
      isPublicGroup: group.is_public_group,
      isCurator: group.is_curator,
    })),
  };
}
