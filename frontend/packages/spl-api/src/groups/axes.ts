import { apiClient, type ApiClient } from "../client";
import { mapCatalogTag, mapLibraryAuthor, mapLibrarySeries } from "../library/mappers";
import { listLibraryAxis } from "../library/requests";
import type { CatalogTag, LibraryAuthor, LibraryAxisQuery, LibrarySeries, LibraryTagQuery } from "../library/types";
import type { CatalogTagResponse, LibraryAuthorResponse, LibrarySeriesResponse } from "../library/wire";
import type { Page } from "../pagination";

function groupAxisPath(groupId: string, axis: "authors" | "series" | "tags"): string {
  return `/api/v1/library/groups/${encodeURIComponent(groupId)}/${axis}/`;
}

export function listGroupAuthors(
  groupId: string,
  query: LibraryAxisQuery = {},
  client: ApiClient = apiClient,
): Promise<Page<LibraryAuthor>> {
  return listLibraryAxis(groupAxisPath(groupId, "authors"), query, mapLibraryAuthor, client);
}

export function listGroupSeries(
  groupId: string,
  query: LibraryAxisQuery = {},
  client: ApiClient = apiClient,
): Promise<Page<LibrarySeries>> {
  return listLibraryAxis(groupAxisPath(groupId, "series"), query, mapLibrarySeries, client);
}

export function listGroupTags(
  groupId: string,
  query: LibraryTagQuery = {},
  client: ApiClient = apiClient,
): Promise<Page<CatalogTag>> {
  return listLibraryAxis(groupAxisPath(groupId, "tags"), query, mapCatalogTag, client);
}
