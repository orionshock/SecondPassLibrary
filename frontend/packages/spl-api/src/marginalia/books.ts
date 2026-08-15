import { apiClient, type ApiClient } from "../client";
import { toPage, type ApiPage, type Page } from "../pagination";
import { mapBookSummary, mapSessionSummary } from "./mappers";
import { bookPath, pageQuery, sessionQuery, withQuery } from "./requests";
import type { MarginaliaBookSessionsPage, MarginaliaBookSummary, MarginaliaPageQuery, MarginaliaSessionsQuery } from "./types";
import type { BookSessionsPageResponse, BookSummaryResponse } from "./wire";

export async function listMarginaliaBooks(query: MarginaliaPageQuery = {}, client: ApiClient = apiClient): Promise<Page<MarginaliaBookSummary>> {
  const response = await client.request<ApiPage<BookSummaryResponse>>(withQuery("/api/v1/marginalia/books/", pageQuery(query)));
  return toPage(response, mapBookSummary);
}

export async function getMarginaliaBook(bookId: string, client: ApiClient = apiClient): Promise<MarginaliaBookSummary> {
  return mapBookSummary(await client.request<BookSummaryResponse>(bookPath(bookId)));
}

export async function listMarginaliaBookSessions(
  bookId: string,
  query: MarginaliaSessionsQuery = {},
  client: ApiClient = apiClient,
): Promise<MarginaliaBookSessionsPage> {
  const response = await client.request<BookSessionsPageResponse>(withQuery(`${bookPath(bookId)}sessions/`, sessionQuery(query)));
  return { ...toPage(response, mapSessionSummary), book: mapBookSummary(response.context.book) };
}
