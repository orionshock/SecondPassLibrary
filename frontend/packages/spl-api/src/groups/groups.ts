import { apiClient, type ApiClient } from "../client";
import { collectPaginatedResults, toPage, type ApiPage, type Page } from "../pagination";
import { mapLibraryGroup, mapPreviewLimitError } from "./mappers";
import type { CreateGroupInput, LibraryGroup, LibraryGroupsQuery, UpdateGroupInput } from "./types";
import type { LibraryGroupResponse } from "./wire";

export async function listGroups(query: LibraryGroupsQuery = {}, client: ApiClient = apiClient): Promise<Page<LibraryGroup>> {
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
    return toPage(await client.request<ApiPage<LibraryGroupResponse>>(`/api/v1/library/groups/${suffix}`), mapLibraryGroup);
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
    return mapLibraryGroup(await client.request<LibraryGroupResponse>(`/api/v1/library/groups/${encodeURIComponent(groupId)}/${suffix}`));
  } catch (error: unknown) {
    throw mapPreviewLimitError(error);
  }
}

export async function createGroup(input: CreateGroupInput, client: ApiClient = apiClient): Promise<LibraryGroup> {
  return mapLibraryGroup(await client.request<LibraryGroupResponse>("/api/v1/library/groups/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: input.name, description: input.description }),
  }));
}

export async function updateGroup(groupId: string, input: UpdateGroupInput, client: ApiClient = apiClient): Promise<LibraryGroup> {
  const body: Record<string, string> = {};
  if (input.name !== undefined) body.name = input.name;
  if (input.description !== undefined) body.description = input.description;
  return mapLibraryGroup(await client.request<LibraryGroupResponse>(`/api/v1/library/groups/${encodeURIComponent(groupId)}/`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }));
}

export async function deleteGroup(groupId: string, client: ApiClient = apiClient): Promise<void> {
  await client.request<void>(`/api/v1/library/groups/${encodeURIComponent(groupId)}/`, { method: "DELETE" });
}

export async function listAllLibraryGroups(client: ApiClient = apiClient): Promise<LibraryGroup[]> {
  return collectPaginatedResults(
    "/api/v1/library/groups/?ordering=name&page_size=200",
    (path) => client.request<ApiPage<LibraryGroupResponse>>(path),
    mapLibraryGroup,
  );
}
