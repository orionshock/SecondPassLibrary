import { apiClient, type ApiClient } from "../client";
import { ApiError } from "../errors";
import { toPage, type ApiPage, type Page } from "../pagination";
import { mapShelfEditorItem, mapShelfItem, mapVisibleShelfEditorItem } from "./mappers";
import type { AddShelfItemInput, ShelfEditorItem, ShelfEditorItemsPage, ShelfEditorItemsQuery, ShelfItem, ShelfItemsQuery } from "./types";
import type { ShelfEditorItemsPageResponse, ShelfItemResponse } from "./wire";

export async function listShelfItems(shelfId: string, query: ShelfItemsQuery = {}, client: ApiClient = apiClient): Promise<Page<ShelfItem>> {
  const parameters = new URLSearchParams();
  if (query.ordering) parameters.set("ordering", query.ordering);
  if (query.page) parameters.set("page", String(query.page));
  if (query.pageSize) parameters.set("page_size", String(query.pageSize));
  const suffix = parameters.size ? `?${parameters.toString()}` : "";
  return toPage(await client.request<ApiPage<ShelfItemResponse>>(`/api/v1/shelves/${encodeURIComponent(shelfId)}/items/${suffix}`), mapShelfItem);
}

export async function listShelfEditorItems(shelfId: string, query: ShelfEditorItemsQuery = {}, client: ApiClient = apiClient): Promise<ShelfEditorItemsPage> {
  const parameters = new URLSearchParams({ view: "edit" });
  if (query.page) parameters.set("page", String(query.page));
  if (query.pageSize) parameters.set("page_size", String(query.pageSize));
  const response = await client.request<ShelfEditorItemsPageResponse>(`/api/v1/shelves/${encodeURIComponent(shelfId)}/items/?${parameters.toString()}`);
  return { ...toPage(response, mapShelfEditorItem), visibleItemCount: response.visible_item_count, unavailableItemCount: response.unavailable_item_count };
}

export async function addShelfItem(shelfId: string, input: AddShelfItemInput, client: ApiClient = apiClient): Promise<ShelfItem> {
  try {
    const response = await client.request<ShelfItemResponse>(`/api/v1/shelves/${encodeURIComponent(shelfId)}/items/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ book: input.bookId }),
    });
    return mapShelfItem(response);
  } catch (error: unknown) {
    if (!(error instanceof ApiError) || !error.fields?.book) throw error;
    const fields: Record<string, string[]> = { ...error.fields, bookId: error.fields.book };
    delete fields.book;
    throw new ApiError(error.message, error.status, { code: error.code, fields });
  }
}

export async function removeShelfItem(shelfId: string, itemId: string, client: ApiClient = apiClient): Promise<void> {
  await client.request<void>(`/api/v1/shelves/${encodeURIComponent(shelfId)}/items/${encodeURIComponent(itemId)}/`, { method: "DELETE" });
}

export async function moveShelfItem(shelfId: string, itemId: string, move: "up" | "down", client: ApiClient = apiClient): Promise<ShelfEditorItem> {
  const response = await client.request<ShelfItemResponse>(`/api/v1/shelves/${encodeURIComponent(shelfId)}/items/${encodeURIComponent(itemId)}/`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ move }),
  });
  return mapVisibleShelfEditorItem(response);
}

export async function setShelfItemPosition(shelfId: string, itemId: string, position: number, client: ApiClient = apiClient): Promise<ShelfEditorItem> {
  const response = await client.request<ShelfItemResponse>(`/api/v1/shelves/${encodeURIComponent(shelfId)}/items/${encodeURIComponent(itemId)}/`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ position }),
  });
  return mapVisibleShelfEditorItem(response);
}
