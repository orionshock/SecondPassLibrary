import { apiClient, type ApiClient } from "./client";
import { mapCompactBook, type CompactBookResponse } from "./compactBooks";
import { ApiError } from "./errors";
import type { BookOrdering, BookPreview, CompactBook } from "./library";
import { collectPaginatedResults, toPage, type ApiPage, type Page } from "./pagination";

export interface LibraryGroup {
  id: string;
  name: string;
  description: string;
  isPublicGroup: boolean;
  previewBooks?: BookPreview[];
}

export interface BookGroupAssignment {
  id: string;
  groupId: string;
  bookId: string;
}

export interface LibraryGroupsQuery {
  q?: string;
  bookId?: string;
  ordering?: "name" | "-name";
  includePreviewBooks?: boolean;
  previewLimit?: number;
  page?: number;
  pageSize?: number;
}

export interface CreateGroupInput {
  name: string;
  description: string;
}

export interface UpdateGroupInput {
  name?: string;
  description?: string;
}

export interface GroupBooksQuery {
  q?: string;
  tag?: string;
  excludeShelfId?: string;
  ordering?: BookOrdering;
  page?: number;
  pageSize?: number;
}

export interface GroupMembersQuery {
  page?: number;
  pageSize?: number;
}

export interface GroupMembership {
  user: { profileId: string; username: string };
  isCurator: boolean;
}

export interface AddGroupMemberInput {
  userId: string;
  isCurator: boolean;
}

export interface UpdateGroupMemberInput {
  isCurator: boolean;
}

interface LibraryGroupResponse {
  id: string;
  name: string;
  description: string;
  is_public_group: boolean;
  preview_books?: BookPreviewResponse[];
}

interface BookPreviewResponse {
  id: string;
  title: string;
  cover_url: string | null;
}

interface GroupMembershipResponse {
  user: { profile_id: string; username: string };
  is_curator: boolean;
  created_at?: string;
  updated_at?: string;
}

interface BookGroupAssignmentResponse {
  id: string;
  group_id: string;
  book_id: string;
}

export async function listGroups(
  query: LibraryGroupsQuery = {},
  client: ApiClient = apiClient,
): Promise<Page<LibraryGroup>> {
  const parameters = new URLSearchParams();
  const search = query.q?.trim();
  if (search) parameters.set("q", search);
  if (query.bookId) parameters.set("book", query.bookId);
  if (query.ordering) parameters.set("ordering", query.ordering);
  if (query.includePreviewBooks) parameters.set("include_preview_books", "true");
  if (query.previewLimit !== undefined) parameters.set("preview_limit", String(query.previewLimit));
  if (query.page) parameters.set("page", String(query.page));
  if (query.pageSize) parameters.set("page_size", String(query.pageSize));
  const suffix = parameters.size ? `?${parameters.toString()}` : "";
  try {
    return toPage(
      await client.request<ApiPage<LibraryGroupResponse>>(`/api/v1/library/groups/${suffix}`),
      mapLibraryGroup,
    );
  } catch (error: unknown) {
    throw mapPreviewLimitError(error);
  }
}

export async function getGroup(
  groupId: string,
  query: { includePreviewBooks?: boolean; previewLimit?: number } = {},
  client: ApiClient = apiClient,
): Promise<LibraryGroup> {
  const parameters = new URLSearchParams();
  if (query.includePreviewBooks) parameters.set("include_preview_books", "true");
  if (query.previewLimit !== undefined) parameters.set("preview_limit", String(query.previewLimit));
  const suffix = parameters.size ? `?${parameters.toString()}` : "";
  try {
    return mapLibraryGroup(await client.request<LibraryGroupResponse>(
      `/api/v1/library/groups/${encodeURIComponent(groupId)}/${suffix}`,
    ));
  } catch (error: unknown) {
    throw mapPreviewLimitError(error);
  }
}

export async function createGroup(
  input: CreateGroupInput,
  client: ApiClient = apiClient,
): Promise<LibraryGroup> {
  const response = await client.request<LibraryGroupResponse>(
    "/api/v1/library/groups/",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: input.name, description: input.description }),
    },
  );
  return mapLibraryGroup(response);
}

export async function updateGroup(
  groupId: string,
  input: UpdateGroupInput,
  client: ApiClient = apiClient,
): Promise<LibraryGroup> {
  const body: Record<string, string> = {};
  if (input.name !== undefined) body.name = input.name;
  if (input.description !== undefined) body.description = input.description;
  const response = await client.request<LibraryGroupResponse>(
    `/api/v1/library/groups/${encodeURIComponent(groupId)}/`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  return mapLibraryGroup(response);
}

export async function deleteGroup(
  groupId: string,
  client: ApiClient = apiClient,
): Promise<void> {
  await client.request<void>(
    `/api/v1/library/groups/${encodeURIComponent(groupId)}/`,
    { method: "DELETE" },
  );
}

export async function listGroupBooks(
  groupId: string,
  query: GroupBooksQuery = {},
  client: ApiClient = apiClient,
): Promise<Page<CompactBook>> {
  const parameters = new URLSearchParams();
  const search = query.q?.trim();
  if (search) parameters.set("q", search);
  if (query.tag) parameters.set("tag", query.tag);
  if (query.excludeShelfId) parameters.set("exclude_shelf", query.excludeShelfId);
  if (query.ordering) parameters.set("ordering", query.ordering);
  if (query.page) parameters.set("page", String(query.page));
  if (query.pageSize) parameters.set("page_size", String(query.pageSize));
  const suffix = parameters.size ? `?${parameters.toString()}` : "";
  return toPage(
    await client.request<ApiPage<CompactBookResponse>>(
      `/api/v1/library/groups/${encodeURIComponent(groupId)}/books/${suffix}`,
    ),
    mapCompactBook,
  );
}

export async function listGroupMembers(
  groupId: string,
  query: GroupMembersQuery = {},
  client: ApiClient = apiClient,
): Promise<Page<GroupMembership>> {
  const parameters = new URLSearchParams();
  if (query.page) parameters.set("page", String(query.page));
  if (query.pageSize) parameters.set("page_size", String(query.pageSize));
  const suffix = parameters.size ? `?${parameters.toString()}` : "";
  return toPage(
    await client.request<ApiPage<GroupMembershipResponse>>(
      `/api/v1/library/groups/${encodeURIComponent(groupId)}/memberships/${suffix}`,
    ),
    mapGroupMembership,
  );
}

export async function addGroupMember(
  groupId: string,
  input: AddGroupMemberInput,
  client: ApiClient = apiClient,
): Promise<GroupMembership> {
  try {
    return mapGroupMembership(await client.request<GroupMembershipResponse>(
      `/api/v1/library/groups/${encodeURIComponent(groupId)}/memberships/`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: input.userId, is_curator: input.isCurator }),
      },
    ));
  } catch (error: unknown) {
    throw mapMembershipError(error);
  }
}

export async function updateGroupMember(
  groupId: string,
  profileId: string,
  input: UpdateGroupMemberInput,
  client: ApiClient = apiClient,
): Promise<GroupMembership> {
  try {
    return mapGroupMembership(await client.request<GroupMembershipResponse>(
      membershipPath(groupId, profileId),
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_curator: input.isCurator }),
      },
    ));
  } catch (error: unknown) {
    throw mapMembershipError(error);
  }
}

export async function removeGroupMember(
  groupId: string,
  profileId: string,
  client: ApiClient = apiClient,
): Promise<void> {
  await client.request<void>(membershipPath(groupId, profileId), { method: "DELETE" });
}

export async function listAllLibraryGroups(client: ApiClient = apiClient): Promise<LibraryGroup[]> {
  return collectPaginatedResults(
    "/api/v1/library/groups/?ordering=name&page_size=200",
    (path) => client.request<ApiPage<LibraryGroupResponse>>(path),
    mapLibraryGroup,
  );
}

export async function listAllGroupsForBook(
  bookId: string,
  previewLimit: number,
  client: ApiClient = apiClient,
): Promise<LibraryGroup[]> {
  const parameters = new URLSearchParams({
    book: bookId,
    ordering: "name",
    include_preview_books: "true",
    preview_limit: String(previewLimit),
    page_size: "200",
  });
  return collectPaginatedResults(
    `/api/v1/library/groups/?${parameters.toString()}`,
    (path) => client.request<ApiPage<LibraryGroupResponse>>(path),
    mapLibraryGroup,
  );
}

export async function addBookToGroup(
  groupId: string,
  bookId: string,
  client: ApiClient = apiClient,
): Promise<BookGroupAssignment> {
  try {
    const response = await client.request<BookGroupAssignmentResponse>(
      `/api/v1/library/groups/${encodeURIComponent(groupId)}/books/`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ book_id: bookId }),
      },
    );
    return mapBookGroupAssignment(response);
  } catch (error: unknown) {
    throw mapBookAssignmentError(error);
  }
}

export async function removeBookFromGroup(
  groupId: string,
  bookId: string,
  client: ApiClient = apiClient,
): Promise<void> {
  await client.request<void>(
    `/api/v1/library/groups/${encodeURIComponent(groupId)}/books/${encodeURIComponent(bookId)}/`,
    { method: "DELETE" },
  );
}

function mapLibraryGroup(response: LibraryGroupResponse): LibraryGroup {
  return {
    id: response.id,
    name: response.name,
    description: response.description,
    isPublicGroup: response.is_public_group,
    ...(response.preview_books === undefined ? {} : {
      previewBooks: response.preview_books.map(({ id, title, cover_url }) => ({
        id,
        title,
        coverUrl: cover_url,
      })),
    }),
  };
}

function mapPreviewLimitError(error: unknown): unknown {
  if (!(error instanceof ApiError) || !error.fields?.preview_limit) return error;
  const { preview_limit: previewLimit, ...fields } = error.fields;
  return new ApiError(error.message, error.status, {
    code: error.code,
    fields: { ...fields, previewLimit },
  });
}

function mapGroupMembership(response: GroupMembershipResponse): GroupMembership {
  return {
    user: { profileId: response.user.profile_id, username: response.user.username },
    isCurator: response.is_curator,
  };
}

function mapBookGroupAssignment(response: BookGroupAssignmentResponse): BookGroupAssignment {
  return { id: response.id, groupId: response.group_id, bookId: response.book_id };
}

function mapBookAssignmentError(error: unknown): unknown {
  if (!(error instanceof ApiError) || !error.fields) return error;
  const originalFields: Record<string, string[]> = error.fields;
  const messages = originalFields.book_id;
  if (!messages) return error;
  const fields: Record<string, string[]> = { ...originalFields, bookId: messages };
  delete fields.book_id;
  return new ApiError(error.message, error.status, { code: error.code, fields });
}

function membershipPath(groupId: string, profileId: string): string {
  return `/api/v1/library/groups/${encodeURIComponent(groupId)}/memberships/${encodeURIComponent(profileId)}/`;
}

function mapMembershipError(error: unknown): unknown {
  if (!(error instanceof ApiError) || !error.fields) return error;
  const aliases: Record<string, string> = { user_id: "userId", is_curator: "isCurator" };
  return new ApiError(error.message, error.status, {
    code: error.code,
    fields: Object.fromEntries(
      Object.entries(error.fields).map(([field, messages]) => [aliases[field] ?? field, messages]),
    ),
  });
}
