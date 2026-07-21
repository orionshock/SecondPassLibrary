import { apiClient, type ApiClient } from "./client";
import { toPage, type ApiPage, type Page } from "./pagination";

export type UserRoleFilter = "owner" | "manager" | "librarian" | "reader" | "curator";
export type CreateUserRole = "manager" | "librarian" | "reader";
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

function mapManagedUser(response: ManagedUserResponse): ManagedUser {
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
