import type { ApiClient } from "../client";
import { ApiError } from "../errors";
import { collectPaginatedResults, toPage, type ApiPage } from "../pagination";
import { mapCatalogTag } from "./mappers";
import type { BookOrdering, CatalogResultPage, LibraryAxisQuery, LibrarySearchOrdering } from "./types";
import type { CatalogResultPageResponse } from "./wire";

interface BookBrowseQueryParameters {
  q?: string;
  tag?: string;
  authorId?: string;
  seriesId?: string;
  publisher?: string;
  excludeShelfId?: string;
  excludeGroupId?: string;
  ordering?: BookOrdering;
  page?: number;
  pageSize?: number;
}

interface BookSearchQueryParameters {
  q: string;
  tag?: string;
  excludeShelfId?: string;
  excludeGroupId?: string;
  ordering?: LibrarySearchOrdering;
  page?: number;
  pageSize?: number;
}

export function withQuery(path: string, parameters: URLSearchParams): string {
  const query = parameters.toString();
  return `${path}${query ? `?${query}` : ""}`;
}

export function bookBrowseParameters(query: BookBrowseQueryParameters): URLSearchParams {
  const parameters = new URLSearchParams();
  const search = query.q?.trim();
  if (search) parameters.set("q", search);
  if (query.tag) parameters.set("tag", query.tag);
  if (query.authorId) parameters.set("author", query.authorId);
  if (query.seriesId) parameters.set("series", query.seriesId);
  if (query.publisher) parameters.set("publisher", query.publisher);
  if (query.excludeShelfId) parameters.set("exclude_shelf", query.excludeShelfId);
  if (query.excludeGroupId) parameters.set("exclude_group", query.excludeGroupId);
  if (query.ordering) parameters.set("ordering", query.ordering);
  if (query.page) parameters.set("page", String(query.page));
  if (query.pageSize) parameters.set("page_size", String(query.pageSize));
  return parameters;
}

export function bookSearchParameters(query: BookSearchQueryParameters): URLSearchParams {
  const parameters = new URLSearchParams({ q: query.q.trim() });
  if (query.tag) parameters.set("tag", query.tag);
  if (query.excludeShelfId) parameters.set("exclude_shelf", query.excludeShelfId);
  if (query.excludeGroupId) parameters.set("exclude_group", query.excludeGroupId);
  if (query.ordering) parameters.set("ordering", query.ordering);
  if (query.page) parameters.set("page", String(query.page));
  if (query.pageSize) parameters.set("page_size", String(query.pageSize));
  return parameters;
}

export async function listLibraryAxis<Response, Item>(
  path: string,
  query: LibraryAxisQuery,
  mapper: (response: Response) => Item,
  client: ApiClient,
): Promise<CatalogResultPage<Item>> {
  const parameters = new URLSearchParams();
  const search = query.q?.trim();
  if (search) parameters.set("q", search);
  if (query.excludeId) parameters.set("exclude_id", query.excludeId);
  if (query.tag) parameters.set("tag", query.tag);
  if (query.ordering) parameters.set("ordering", query.ordering);
  if (query.includePreviewBooks) parameters.set("include_preview_books", "true");
  if (query.previewLimit !== undefined) parameters.set("preview_limit", String(query.previewLimit));
  if (query.page) parameters.set("page", String(query.page));
  if (query.pageSize) parameters.set("page_size", String(query.pageSize));
  try {
    return toCatalogResultPage(
      await client.request<CatalogResultPageResponse<Response>>(withQuery(path, parameters)),
      mapper,
    );
  } catch (error: unknown) {
    if (!(error instanceof ApiError) || (!error.fields?.preview_limit && !error.fields?.exclude_id)) throw error;
    const { preview_limit: previewLimit, exclude_id: excludeId, ...fields } = error.fields;
    throw new ApiError(error.message, error.status, {
      code: error.code,
      fields: {
        ...fields,
        ...(previewLimit ? { previewLimit } : {}),
        ...(excludeId ? { excludeId } : {}),
      },
    });
  }
}

export function toCatalogResultPage<Response, Item>(
  page: CatalogResultPageResponse<Response>,
  mapper: (response: Response) => Item,
): CatalogResultPage<Item> {
  return {
    ...toPage(page, mapper),
    catalogTags: (page.catalog_tags ?? []).map(mapCatalogTag),
  };
}

export async function listAllLibraryAxis<Response, Item>(
  path: string,
  mapper: (response: Response) => Item,
  client: ApiClient,
): Promise<Item[]> {
  return collectPaginatedResults(
    `${path}?ordering=name&page_size=200`,
    (next) => client.request<ApiPage<Response>>(next),
    mapper,
  );
}

export async function mutateLibraryAxis<Response, Item>(
  path: string,
  method: "POST" | "PATCH",
  payload: Record<string, string>,
  mapper: (response: Response) => Item,
  client: ApiClient,
): Promise<Item> {
  try {
    const response = await client.request<Response>(path, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return mapper(response);
  } catch (error: unknown) {
    if (!(error instanceof ApiError) || !error.fields) throw error;
    throw new ApiError(error.message, error.status, {
      code: error.code,
      fields: Object.fromEntries(
        Object.entries(error.fields).map(([field, messages]) => [
          field === "sort_name" ? "sortName" : field,
          messages,
        ]),
      ),
    });
  }
}
