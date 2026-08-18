import { apiClient, type ApiClient } from "../client";
import { ApiError } from "../errors";
import { toPage, type ApiPage, type Page } from "../pagination";
import { mapCompactBook, type CompactBookResponse } from "./compactBooks";
import { mapBookDetail } from "./mappers";
import { bookBrowseParameters, bookSearchParameters, withQuery } from "./requests";
import type { BookDetail, CompactBook, LibraryBookSearchQuery, LibraryBooksQuery, UpdateBookInput } from "./types";
import type { BookDetailResponse } from "./wire";

export async function listBooks(query: LibraryBooksQuery = {}, client: ApiClient = apiClient): Promise<Page<CompactBook>> {
  const parameters = bookBrowseParameters(query);
  return toPage(
    await client.request<ApiPage<CompactBookResponse>>(withQuery("/api/v1/library/books/", parameters)),
    mapCompactBook,
  );
}

export async function searchLibraryBooks(
  query: LibraryBookSearchQuery,
  client: ApiClient = apiClient,
): Promise<Page<CompactBook>> {
  const parameters = bookSearchParameters(query);
  return toPage(
    await client.request<ApiPage<CompactBookResponse>>(
      withQuery("/api/v1/library/search", parameters),
    ),
    mapCompactBook,
  );
}

export async function getBook(bookId: string, client: ApiClient = apiClient): Promise<BookDetail> {
  const response = await client.request<BookDetailResponse>(
    `/api/v1/library/books/${encodeURIComponent(bookId)}/`,
  );
  return mapBookDetail(response);
}

export async function updateBook(bookId: string, input: UpdateBookInput, client: ApiClient = apiClient): Promise<BookDetail> {
  const payload: Record<string, unknown> = {};
  const fields: Array<[keyof UpdateBookInput, string]> = [
    ["title", "title"], ["sortTitle", "sort_title"], ["subtitle", "subtitle"],
    ["description", "description"], ["publisher", "publisher"], ["language", "language"],
    ["publishedYear", "published_year"], ["publishedMonth", "published_month"],
    ["publishedDay", "published_day"], ["publishedDatePrecision", "published_date_precision"],
    ["authorIds", "authors"], ["seriesId", "series"], ["seriesIndex", "series_index"],
    ["catalogTagNames", "catalog_tags"],
  ];
  for (const [appField, wireField] of fields) {
    if (input[appField] !== undefined) payload[wireField] = input[appField];
  }
  if (input.identifiers !== undefined) {
    payload.identifiers = input.identifiers.map(({ scheme, value }) => ({ scheme, value }));
  }
  try {
    return mapBookDetail(await client.request<BookDetailResponse>(
      `/api/v1/library/books/${encodeURIComponent(bookId)}/`,
      { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) },
    ));
  } catch (error: unknown) {
    if (!(error instanceof ApiError) || !error.fields) throw error;
    const aliases: Record<string, string> = {
      authors: "authorIds", series: "seriesId", catalogTags: "catalogTagNames",
    };
    throw new ApiError(error.message, error.status, {
      code: error.code,
      fields: Object.fromEntries(Object.entries(error.fields).map(([field, messages]) => [aliases[field] ?? field, messages])),
    });
  }
}

export async function replaceBookCover(
  bookId: string,
  file: File,
  client: ApiClient = apiClient,
): Promise<BookDetail> {
  const body = new FormData();
  body.append("cover", file);
  return mapBookDetail(await client.request<BookDetailResponse>(
    `/api/v1/library/books/${encodeURIComponent(bookId)}/cover/`,
    { method: "POST", body },
  ));
}

export async function clearBookCover(
  bookId: string,
  client: ApiClient = apiClient,
): Promise<BookDetail> {
  return mapBookDetail(await client.request<BookDetailResponse>(
    `/api/v1/library/books/${encodeURIComponent(bookId)}/cover/`,
    { method: "DELETE" },
  ));
}
