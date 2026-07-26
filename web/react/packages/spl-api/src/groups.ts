import { apiClient, type ApiClient } from "./client";
import { ApiError } from "./errors";
import { toPage, type ApiPage, type Page } from "./pagination";

export interface LibraryGroup {
  id: string;
  name: string;
  description: string;
  isPublicGroup: boolean;
}

export interface BookGroupAssignment {
  id: string;
  groupId: string;
  bookId: string;
}

export interface LibraryGroupsQuery {
  q?: string;
  ordering?: "name" | "-name";
  page?: number;
  pageSize?: number;
}

interface LibraryGroupResponse {
  id: string;
  name: string;
  description: string;
  is_public_group: boolean;
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
  if (query.page) parameters.set("page", String(query.page));
  if (query.pageSize) parameters.set("page_size", String(query.pageSize));
  const suffix = parameters.size ? `?${parameters.toString()}` : "";
  return toPage(
    await client.request<ApiPage<LibraryGroupResponse>>(`/api/v1/library/groups/${suffix}`),
    mapLibraryGroup,
  );
}

export async function listAllLibraryGroups(client: ApiClient = apiClient): Promise<LibraryGroup[]> {
  const groups: LibraryGroup[] = [];
  let path: string | null = "/api/v1/library/groups/?ordering=name&page_size=200";
  while (path) {
    const page: ApiPage<LibraryGroupResponse> = await client.request<ApiPage<LibraryGroupResponse>>(path);
    groups.push(...page.results.map(mapLibraryGroup));
    path = page.next;
  }
  return groups;
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
