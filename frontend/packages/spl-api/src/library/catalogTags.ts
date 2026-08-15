import { apiClient, type ApiClient } from "../client";
import { collectPaginatedResults, toPage, type ApiPage, type Page } from "../pagination";
import { mapCatalogTag } from "./mappers";
import { withQuery } from "./requests";
import type { CatalogTag } from "./types";
import type { CatalogTagResponse } from "./wire";

export async function listCatalogTags(
  query: { ordering?: "name" | "-name" | "book_count" | "-book_count"; page?: number; pageSize?: number } = {},
  client: ApiClient = apiClient,
): Promise<Page<CatalogTag>> {
  const parameters = new URLSearchParams();
  if (query.ordering) parameters.set("ordering", query.ordering);
  if (query.page) parameters.set("page", String(query.page));
  if (query.pageSize) parameters.set("page_size", String(query.pageSize));
  return toPage(
    await client.request<ApiPage<CatalogTagResponse>>(withQuery("/api/v1/library/tags/", parameters)),
    mapCatalogTag,
  );
}

export async function listAllCatalogTags(client: ApiClient = apiClient): Promise<CatalogTag[]> {
  return collectPaginatedResults(
    "/api/v1/library/tags/?ordering=name&page_size=200",
    (path) => client.request<ApiPage<CatalogTagResponse>>(path),
    mapCatalogTag,
  );
}

