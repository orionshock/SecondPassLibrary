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
  ordering?: "name" | "-name";
  includePreviewBooks?: boolean;
  page?: number;
  pageSize?: number;
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
  if (query.ordering) parameters.set("ordering", query.ordering);
  if (query.includePreviewBooks) parameters.set("include_preview_books", "true");
  if (query.page) parameters.set("page", String(query.page));
  if (query.pageSize) parameters.set("page_size", String(query.pageSize));
  const suffix = parameters.size ? `?${parameters.toString()}` : "";
  return toPage(
    await client.request<ApiPage<LibraryGroupResponse>>(`/api/v1/library/groups/${suffix}`),
    mapLibraryGroup,
  );
}

export async function getGroup(
  groupId: string,
  query: { includePreviewBooks?: boolean } = {},
  client: ApiClient = apiClient,
): Promise<LibraryGroup> {
  const parameters = new URLSearchParams();
  if (query.includePreviewBooks) parameters.set("include_preview_books", "true");
  const suffix = parameters.size ? `?${parameters.toString()}` : "";
  return mapLibraryGroup(await client.request<LibraryGroupResponse>(
    `/api/v1/library/groups/${encodeURIComponent(groupId)}/${suffix}`,
  ));
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

export async function listAllLibraryGroups(client: ApiClient = apiClient): Promise<LibraryGroup[]> {
  return collectPaginatedResults(
    "/api/v1/library/groups/?ordering=name&page_size=200",
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
