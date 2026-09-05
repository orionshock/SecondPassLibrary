import { apiClient, type ApiClient } from "../client";
import { mapLibraryAuthor, mapLibrarySeries } from "./mappers";
import { listAllLibraryAxis, listLibraryAxis, mutateLibraryAxis } from "./requests";
import type { AuthorMutationInput, CatalogResultPage, LibraryAuthor, LibraryAxisQuery, LibrarySeries, SeriesMutationInput } from "./types";
import type { LibraryAuthorResponse, LibrarySeriesResponse } from "./wire";

export async function listAuthors(query: LibraryAxisQuery = {}, client: ApiClient = apiClient): Promise<CatalogResultPage<LibraryAuthor>> {
  return listLibraryAxis("/api/v1/library/authors/", query, mapLibraryAuthor, client);
}

export async function listSeries(query: LibraryAxisQuery = {}, client: ApiClient = apiClient): Promise<CatalogResultPage<LibrarySeries>> {
  return listLibraryAxis("/api/v1/library/series/", query, mapLibrarySeries, client);
}

export async function getAuthor(authorId: string, client: ApiClient = apiClient): Promise<LibraryAuthor> {
  return mapLibraryAuthor(await client.request<LibraryAuthorResponse>(
    `/api/v1/library/authors/${encodeURIComponent(authorId)}/`,
  ));
}

export async function createAuthor(input: AuthorMutationInput, client: ApiClient = apiClient): Promise<LibraryAuthor> {
  return mutateLibraryAxis(
    "/api/v1/library/authors/",
    "POST",
    { name: input.name, sort_name: input.sortName, biography: input.biography },
    mapLibraryAuthor,
    client,
  );
}

export async function updateAuthor(authorId: string, input: AuthorMutationInput, client: ApiClient = apiClient): Promise<LibraryAuthor> {
  return mutateLibraryAxis(
    `/api/v1/library/authors/${encodeURIComponent(authorId)}/`,
    "PATCH",
    { name: input.name, sort_name: input.sortName, biography: input.biography },
    mapLibraryAuthor,
    client,
  );
}

export async function deleteAuthor(authorId: string, client: ApiClient = apiClient): Promise<void> {
  await client.request<void>(`/api/v1/library/authors/${encodeURIComponent(authorId)}/`, {
    method: "DELETE",
  });
}

export async function getSeries(seriesId: string, client: ApiClient = apiClient): Promise<LibrarySeries> {
  return mapLibrarySeries(await client.request<LibrarySeriesResponse>(
    `/api/v1/library/series/${encodeURIComponent(seriesId)}/`,
  ));
}

export async function createSeries(input: SeriesMutationInput, client: ApiClient = apiClient): Promise<LibrarySeries> {
  return mutateLibraryAxis(
    "/api/v1/library/series/",
    "POST",
    { name: input.name, sort_name: input.sortName, summary: input.summary },
    mapLibrarySeries,
    client,
  );
}

export async function updateSeries(seriesId: string, input: SeriesMutationInput, client: ApiClient = apiClient): Promise<LibrarySeries> {
  return mutateLibraryAxis(
    `/api/v1/library/series/${encodeURIComponent(seriesId)}/`,
    "PATCH",
    { name: input.name, sort_name: input.sortName, summary: input.summary },
    mapLibrarySeries,
    client,
  );
}

export async function deleteSeries(seriesId: string, client: ApiClient = apiClient): Promise<void> {
  await client.request<void>(`/api/v1/library/series/${encodeURIComponent(seriesId)}/`, {
    method: "DELETE",
  });
}

export function listAllAuthors(client: ApiClient = apiClient): Promise<LibraryAuthor[]> {
  return listAllLibraryAxis("/api/v1/library/authors/", mapLibraryAuthor, client);
}

export function listAllSeries(client: ApiClient = apiClient): Promise<LibrarySeries[]> {
  return listAllLibraryAxis("/api/v1/library/series/", mapLibrarySeries, client);
}
