import { apiClient, type ApiClient } from "../client";
import { mapCompactBook, type CompactBookResponse } from "../library/compactBooks";
import type { CatalogResultPage, CompactBook } from "../library";
import { bookBrowseParameters, bookSearchParameters, toCatalogResultPage, withQuery } from "../library/requests";
import type { CatalogResultPageResponse } from "../library/wire";
import { collectPaginatedResults, type ApiPage } from "../pagination";
import { mapBookAssignmentError, mapBookGroupAssignment, mapLibraryGroup } from "./mappers";
import type { BookGroupAssignment, GroupBooksQuery, GroupBookSearchQuery, LibraryGroup } from "./types";
import type { BookGroupAssignmentResponse, LibraryGroupResponse } from "./wire";

export async function listGroupBooks(groupId: string, query: GroupBooksQuery = {}, client: ApiClient = apiClient): Promise<CatalogResultPage<CompactBook>> {
  const parameters = bookBrowseParameters(query);
  return toCatalogResultPage(
    await client.request<CatalogResultPageResponse<CompactBookResponse>>(withQuery(`/api/v1/library/groups/${encodeURIComponent(groupId)}/books/`, parameters)),
    mapCompactBook,
  );
}

export async function searchGroupBooks(
  groupId: string,
  query: GroupBookSearchQuery,
  client: ApiClient = apiClient,
): Promise<CatalogResultPage<CompactBook>> {
  return toCatalogResultPage(
    await client.request<CatalogResultPageResponse<CompactBookResponse>>(withQuery(
      `/api/v1/library/groups/${encodeURIComponent(groupId)}/search`,
      bookSearchParameters(query),
    )),
    mapCompactBook,
  );
}

export async function listAllGroupsForBook(bookId: string, previewLimit: number, client: ApiClient = apiClient): Promise<LibraryGroup[]> {
  const parameters = new URLSearchParams({
    book: bookId,
    ordering: "name",
    include_preview_books: "true",
    preview_limit: String(previewLimit),
    page_size: "200",
  });
  return collectPaginatedResults(
    `/api/v1/library/groups/?${parameters.toString()}`,
    (path) => client.request<ApiPage<LibraryGroupResponse>>(path),
    mapLibraryGroup,
  );
}

export async function addBookToGroup(groupId: string, bookId: string, client: ApiClient = apiClient): Promise<BookGroupAssignment> {
  try {
    const response = await client.request<BookGroupAssignmentResponse>(`/api/v1/library/groups/${encodeURIComponent(groupId)}/books/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ book_id: bookId }),
    });
    return mapBookGroupAssignment(response);
  } catch (error: unknown) {
    throw mapBookAssignmentError(error);
  }
}

export async function removeBookFromGroup(groupId: string, bookId: string, client: ApiClient = apiClient): Promise<void> {
  await client.request<void>(`/api/v1/library/groups/${encodeURIComponent(groupId)}/books/${encodeURIComponent(bookId)}/`, { method: "DELETE" });
}
