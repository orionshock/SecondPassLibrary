import { apiClient, type ApiClient } from "../client";
import { ApiError } from "../errors";
import { collectPaginatedResults, toPage, type ApiPage, type Page } from "../pagination";
import { mapPreviewLimitError, mapShelfSummary } from "./mappers";
import type { CreateShelfInput, ShelvesQuery, ShelfSummary, UpdateShelfInput } from "./types";
import type { ShelfSummaryResponse } from "./wire";

export async function listShelves(query: ShelvesQuery = {}, client: ApiClient = apiClient): Promise<Page<ShelfSummary>> {
  const parameters = new URLSearchParams();
  if (query.scope) parameters.set("scope", query.scope);
  if (query.ownerGroupId) parameters.set("owner_group", query.ownerGroupId);
  if (query.bookId) parameters.set("book", query.bookId);
  if (query.ordering) parameters.set("ordering", query.ordering);
  if (query.includePreviewBooks) parameters.set("include_preview_books", "true");
  if (query.previewLimit !== undefined) parameters.set("preview_limit", String(query.previewLimit));
  if (query.page) parameters.set("page", String(query.page));
  if (query.pageSize) parameters.set("page_size", String(query.pageSize));
  const suffix = parameters.size ? `?${parameters.toString()}` : "";
  try {
    return toPage(await client.request<ApiPage<ShelfSummaryResponse>>(`/api/v1/shelves/${suffix}`), mapShelfSummary);
  } catch (error: unknown) {
    throw mapPreviewLimitError(error);
  }
}

export async function getShelf(
  shelfId: string,
  query: { includePreviewBooks?: boolean; previewLimit?: number } = {},
  client: ApiClient = apiClient,
): Promise<ShelfSummary> {
  const parameters = new URLSearchParams();
  if (query.includePreviewBooks) parameters.set("include_preview_books", "true");
  if (query.previewLimit !== undefined) parameters.set("preview_limit", String(query.previewLimit));
  const suffix = parameters.size ? `?${parameters.toString()}` : "";
  try {
    return mapShelfSummary(await client.request<ShelfSummaryResponse>(`/api/v1/shelves/${encodeURIComponent(shelfId)}/${suffix}`));
  } catch (error: unknown) {
    throw mapPreviewLimitError(error);
  }
}

export async function listAllShelvesForBook(bookId: string, previewLimit: number, client: ApiClient = apiClient): Promise<ShelfSummary[]> {
  const parameters = new URLSearchParams({ book: bookId, ordering: "name", include_preview_books: "true", preview_limit: String(previewLimit), page_size: "200" });
  return collectPaginatedResults(`/api/v1/shelves/?${parameters.toString()}`, (path) => client.request<ApiPage<ShelfSummaryResponse>>(path), mapShelfSummary);
}

export async function listAllGroupShelvesForBook(bookId: string, client: ApiClient = apiClient): Promise<ShelfSummary[]> {
  const parameters = new URLSearchParams({ scope: "group", book: bookId, ordering: "name", page_size: "200" });
  return collectPaginatedResults(`/api/v1/shelves/?${parameters.toString()}`, (path) => client.request<ApiPage<ShelfSummaryResponse>>(path), mapShelfSummary);
}

export async function createShelf(input: CreateShelfInput, client: ApiClient = apiClient): Promise<ShelfSummary> {
  const payload: Record<string, unknown> = { name: input.name, description: input.description, owner_type: input.ownerType, visibility: input.visibility };
  if (input.ownerGroupId !== undefined) payload.owner_group = input.ownerGroupId;
  return mutateShelf("/api/v1/shelves/", "POST", payload, client);
}

export async function updateShelf(shelfId: string, input: UpdateShelfInput, client: ApiClient = apiClient): Promise<ShelfSummary> {
  const payload: Record<string, unknown> = {};
  if (input.name !== undefined) payload.name = input.name;
  if (input.description !== undefined) payload.description = input.description;
  if (input.visibility !== undefined) payload.visibility = input.visibility;
  return mutateShelf(`/api/v1/shelves/${encodeURIComponent(shelfId)}/`, "PATCH", payload, client);
}

export async function deleteShelf(shelfId: string, client: ApiClient = apiClient): Promise<void> {
  await client.request<void>(`/api/v1/shelves/${encodeURIComponent(shelfId)}/`, { method: "DELETE" });
}

async function mutateShelf(path: string, method: "POST" | "PATCH", payload: Record<string, unknown>, client: ApiClient): Promise<ShelfSummary> {
  try {
    return mapShelfSummary(await client.request<ShelfSummaryResponse>(path, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }));
  } catch (error: unknown) {
    if (!(error instanceof ApiError) || !error.fields) throw error;
    const aliases: Record<string, string> = { owner_type: "ownerType", owner_group: "ownerGroupId" };
    throw new ApiError(error.message, error.status, {
      code: error.code,
      fields: Object.fromEntries(Object.entries(error.fields).map(([field, messages]) => [aliases[field] ?? field, messages])),
    });
  }
}
