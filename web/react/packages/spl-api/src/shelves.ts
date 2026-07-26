import { apiClient, type ApiClient } from "./client";
import { mapCompactBook, type CompactBookResponse } from "./compactBooks";
import { ApiError } from "./errors";
import type { BookPreview, CompactBook } from "./library";
import { collectPaginatedResults, toPage, type ApiPage, type Page } from "./pagination";

export type ShelfOwnerType = "user" | "group";
export type ShelfVisibility = "private" | "listed";
export type ShelfOrdering = "name" | "-item_count";
export type ShelfScope = "personal" | "shared" | "group";
export type ShelfItemOrdering = "position" | "title" | "author";

export interface ShelfOwnerUser {
  profileId: string;
  username: string;
}

export interface ShelfOwnerGroup {
  id: string;
  name: string;
  isPublicGroup: boolean;
}

export interface ShelfSummary {
  id: string;
  name: string;
  description: string;
  ownerType: ShelfOwnerType;
  ownerUser: ShelfOwnerUser | null;
  ownerGroup: ShelfOwnerGroup | null;
  visibility: ShelfVisibility;
  itemCount: number;
  matchedItemId?: string | null;
  canEdit: boolean;
  previewBooks?: BookPreview[];
}

export interface CreateShelfInput {
  name: string;
  description: string;
  ownerType: ShelfOwnerType;
  ownerGroupId?: string;
  visibility: ShelfVisibility;
}

export interface UpdateShelfInput {
  name?: string;
  description?: string;
  visibility?: ShelfVisibility;
}

export interface AddShelfItemInput {
  bookId: string;
}

export interface ShelvesQuery {
  scope?: ShelfScope;
  ownerGroupId?: string;
  bookId?: string;
  ordering?: ShelfOrdering;
  includePreviewBooks?: boolean;
  page?: number;
  pageSize?: number;
}

export interface ShelfItemsQuery {
  ordering?: ShelfItemOrdering;
  page?: number;
  pageSize?: number;
}

export interface ShelfEditorItemsQuery {
  page?: number;
  pageSize?: number;
}

export interface ShelfItem {
  id: string;
  shelfId: string;
  book: CompactBook;
  position: number;
  addedBy: ShelfOwnerUser | null;
}

export type ShelfEditorItem =
  | {
    id: string;
    shelfId: string;
    position: number;
    unavailable: false;
    book: CompactBook;
    addedBy: ShelfOwnerUser | null;
  }
  | {
    id: string;
    shelfId: string;
    position: number;
    unavailable: true;
    book: null;
    addedBy: ShelfOwnerUser | null;
  };

export interface ShelfEditorItemsPage extends Page<ShelfEditorItem> {
  visibleItemCount: number;
  unavailableItemCount: number;
}

interface ShelfOwnerUserResponse {
  profile_id: string;
  username: string;
}

interface ShelfOwnerGroupResponse {
  id: string;
  name: string;
  is_public_group: boolean;
}

interface ShelfSummaryResponse {
  id: string;
  name: string;
  description: string;
  owner_type: ShelfOwnerType;
  owner_user: ShelfOwnerUserResponse | null;
  owner_group: ShelfOwnerGroupResponse | null;
  visibility: ShelfVisibility;
  item_count: number;
  matched_item_id?: string | null;
  can_edit: boolean;
  preview_books?: BookPreviewResponse[];
}

interface BookPreviewResponse {
  id: string;
  title: string;
  cover_url: string | null;
}

interface ShelfItemResponse {
  id: string;
  shelf: string;
  book: CompactBookResponse;
  position: number;
  added_by: ShelfOwnerUserResponse | null;
}

interface ShelfEditorItemResponse {
  id: string;
  shelf: string;
  book: CompactBookResponse | null;
  position: number;
  unavailable: boolean;
  added_by: ShelfOwnerUserResponse | null;
}

interface ShelfEditorItemsPageResponse extends ApiPage<ShelfEditorItemResponse> {
  visible_item_count: number;
  unavailable_item_count: number;
}

export async function listShelves(
  query: ShelvesQuery = {},
  client: ApiClient = apiClient,
): Promise<Page<ShelfSummary>> {
  const parameters = new URLSearchParams();
  if (query.scope) parameters.set("scope", query.scope);
  if (query.ownerGroupId) parameters.set("owner_group", query.ownerGroupId);
  if (query.bookId) parameters.set("book", query.bookId);
  if (query.ordering) parameters.set("ordering", query.ordering);
  if (query.includePreviewBooks) parameters.set("include_preview_books", "true");
  if (query.page) parameters.set("page", String(query.page));
  if (query.pageSize) parameters.set("page_size", String(query.pageSize));
  const suffix = parameters.size ? `?${parameters.toString()}` : "";
  return toPage(
    await client.request<ApiPage<ShelfSummaryResponse>>(`/api/v1/shelves/${suffix}`),
    mapShelfSummary,
  );
}

export async function getShelf(
  shelfId: string,
  query: { includePreviewBooks?: boolean } = {},
  client: ApiClient = apiClient,
): Promise<ShelfSummary> {
  const parameters = new URLSearchParams();
  if (query.includePreviewBooks) parameters.set("include_preview_books", "true");
  const suffix = parameters.size ? `?${parameters.toString()}` : "";
  return mapShelfSummary(await client.request<ShelfSummaryResponse>(
    `/api/v1/shelves/${encodeURIComponent(shelfId)}/${suffix}`,
  ));
}

export async function listShelfItems(
  shelfId: string,
  query: ShelfItemsQuery = {},
  client: ApiClient = apiClient,
): Promise<Page<ShelfItem>> {
  const parameters = new URLSearchParams();
  if (query.ordering) parameters.set("ordering", query.ordering);
  if (query.page) parameters.set("page", String(query.page));
  if (query.pageSize) parameters.set("page_size", String(query.pageSize));
  const suffix = parameters.size ? `?${parameters.toString()}` : "";
  return toPage(
    await client.request<ApiPage<ShelfItemResponse>>(
      `/api/v1/shelves/${encodeURIComponent(shelfId)}/items/${suffix}`,
    ),
    mapShelfItem,
  );
}

export async function listShelfEditorItems(
  shelfId: string,
  query: ShelfEditorItemsQuery = {},
  client: ApiClient = apiClient,
): Promise<ShelfEditorItemsPage> {
  const parameters = new URLSearchParams({ view: "edit" });
  if (query.page) parameters.set("page", String(query.page));
  if (query.pageSize) parameters.set("page_size", String(query.pageSize));
  const response = await client.request<ShelfEditorItemsPageResponse>(
    `/api/v1/shelves/${encodeURIComponent(shelfId)}/items/?${parameters.toString()}`,
  );
  return {
    ...toPage(response, mapShelfEditorItem),
    visibleItemCount: response.visible_item_count,
    unavailableItemCount: response.unavailable_item_count,
  };
}

export async function listAllShelvesForBook(
  bookId: string,
  client: ApiClient = apiClient,
): Promise<ShelfSummary[]> {
  const parameters = new URLSearchParams({
    book: bookId,
    ordering: "name",
    page_size: "200",
  });
  return collectPaginatedResults(
    `/api/v1/shelves/?${parameters.toString()}`,
    (path) => client.request<ApiPage<ShelfSummaryResponse>>(path),
    mapShelfSummary,
  );
}

export async function createShelf(
  input: CreateShelfInput,
  client: ApiClient = apiClient,
): Promise<ShelfSummary> {
  const payload: Record<string, unknown> = {
    name: input.name,
    description: input.description,
    owner_type: input.ownerType,
    visibility: input.visibility,
  };
  if (input.ownerGroupId !== undefined) payload.owner_group = input.ownerGroupId;
  return mutateShelf("/api/v1/shelves/", "POST", payload, client);
}

export async function updateShelf(
  shelfId: string,
  input: UpdateShelfInput,
  client: ApiClient = apiClient,
): Promise<ShelfSummary> {
  const payload: Record<string, unknown> = {};
  if (input.name !== undefined) payload.name = input.name;
  if (input.description !== undefined) payload.description = input.description;
  if (input.visibility !== undefined) payload.visibility = input.visibility;
  return mutateShelf(
    `/api/v1/shelves/${encodeURIComponent(shelfId)}/`,
    "PATCH",
    payload,
    client,
  );
}

export async function deleteShelf(
  shelfId: string,
  client: ApiClient = apiClient,
): Promise<void> {
  await client.request<void>(
    `/api/v1/shelves/${encodeURIComponent(shelfId)}/`,
    { method: "DELETE" },
  );
}

export async function addShelfItem(
  shelfId: string,
  input: AddShelfItemInput,
  client: ApiClient = apiClient,
): Promise<ShelfItem> {
  try {
    const response = await client.request<ShelfItemResponse>(
      `/api/v1/shelves/${encodeURIComponent(shelfId)}/items/`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ book: input.bookId }),
      },
    );
    return mapShelfItem(response);
  } catch (error: unknown) {
    if (!(error instanceof ApiError) || !error.fields?.book) throw error;
    const fields: Record<string, string[]> = { ...error.fields, bookId: error.fields.book };
    delete fields.book;
    throw new ApiError(error.message, error.status, { code: error.code, fields });
  }
}

export async function removeShelfItem(
  shelfId: string,
  itemId: string,
  client: ApiClient = apiClient,
): Promise<void> {
  await client.request<void>(
    `/api/v1/shelves/${encodeURIComponent(shelfId)}/items/${encodeURIComponent(itemId)}/`,
    { method: "DELETE" },
  );
}

export async function moveShelfItem(
  shelfId: string,
  itemId: string,
  move: "up" | "down",
  client: ApiClient = apiClient,
): Promise<ShelfEditorItem> {
  const response = await client.request<ShelfItemResponse>(
    `/api/v1/shelves/${encodeURIComponent(shelfId)}/items/${encodeURIComponent(itemId)}/`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ move }),
    },
  );
  return mapVisibleShelfEditorItem(response);
}

function mapShelfSummary(response: ShelfSummaryResponse): ShelfSummary {
  return {
    id: response.id,
    name: response.name,
    description: response.description,
    ownerType: response.owner_type,
    ownerUser: response.owner_user ? {
      profileId: response.owner_user.profile_id,
      username: response.owner_user.username,
    } : null,
    ownerGroup: response.owner_group ? {
      id: response.owner_group.id,
      name: response.owner_group.name,
      isPublicGroup: response.owner_group.is_public_group,
    } : null,
    visibility: response.visibility,
    itemCount: response.item_count,
    ...(response.matched_item_id !== undefined ? { matchedItemId: response.matched_item_id } : {}),
    canEdit: response.can_edit,
    ...(response.preview_books === undefined ? {} : {
      previewBooks: response.preview_books.map(({ id, title, cover_url }) => ({
        id,
        title,
        coverUrl: cover_url,
      })),
    }),
  };
}

function mapShelfItem(response: ShelfItemResponse): ShelfItem {
  return {
    id: response.id,
    shelfId: response.shelf,
    book: mapCompactBook(response.book),
    position: response.position,
    addedBy: response.added_by ? {
      profileId: response.added_by.profile_id,
      username: response.added_by.username,
    } : null,
  };
}

function mapShelfEditorItem(response: ShelfEditorItemResponse): ShelfEditorItem {
  const addedBy = mapShelfOwnerUser(response.added_by);
  if (response.unavailable || response.book === null) {
    return {
      id: response.id,
      shelfId: response.shelf,
      position: response.position,
      unavailable: true,
      book: null,
      addedBy,
    };
  }
  return {
    id: response.id,
    shelfId: response.shelf,
    position: response.position,
    unavailable: false,
    book: mapCompactBook(response.book),
    addedBy,
  };
}

function mapVisibleShelfEditorItem(response: ShelfItemResponse): ShelfEditorItem {
  return {
    ...mapShelfItem(response),
    unavailable: false,
  };
}

function mapShelfOwnerUser(response: ShelfOwnerUserResponse | null): ShelfOwnerUser | null {
  return response ? {
    profileId: response.profile_id,
    username: response.username,
  } : null;
}

async function mutateShelf(
  path: string,
  method: "POST" | "PATCH",
  payload: Record<string, unknown>,
  client: ApiClient,
): Promise<ShelfSummary> {
  try {
    return mapShelfSummary(await client.request<ShelfSummaryResponse>(path, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }));
  } catch (error: unknown) {
    if (!(error instanceof ApiError) || !error.fields) throw error;
    const aliases: Record<string, string> = {
      owner_type: "ownerType",
      owner_group: "ownerGroupId",
    };
    throw new ApiError(error.message, error.status, {
      code: error.code,
      fields: Object.fromEntries(
        Object.entries(error.fields).map(([field, messages]) => [
          aliases[field] ?? field,
          messages,
        ]),
      ),
    });
  }
}
