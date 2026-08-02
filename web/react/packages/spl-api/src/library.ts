import { apiClient, type ApiClient } from "./client";
import { mapCompactBook, type CompactBookResponse } from "./compactBooks";
import { ApiError } from "./errors";
import { collectPaginatedResults, toPage, type ApiPage, type Page } from "./pagination";
import { sameOriginUrl } from "./urls";

export type BookOrdering =
  | "title" | "-title"
  | "author" | "-author"
  | "series" | "-series"
  | "series_index" | "-series_index"
  | "publisher" | "-publisher";

export interface LibraryBooksQuery {
  q?: string;
  tag?: string;
  authorId?: string;
  seriesId?: string;
  ordering?: BookOrdering;
  page?: number;
  pageSize?: number;
}

export interface LibraryBookSearchQuery {
  q: string;
  excludeShelfId?: string;
  excludeGroupId?: string;
  ordering?: BookOrdering;
  page?: number;
  pageSize?: number;
}

export type LibraryAxisOrdering = "name" | "-name" | "book_count" | "-book_count";

export interface LibraryAxisQuery {
  q?: string;
  tag?: string;
  ordering?: LibraryAxisOrdering;
  includePreviewBooks?: boolean;
  previewLimit?: number;
  page?: number;
  pageSize?: number;
}

export interface AuthorMutationInput {
  name: string;
  sortName: string;
  biography: string;
}

export interface SeriesMutationInput {
  name: string;
  sortName: string;
  summary: string;
}

export const bookIdentifierSchemes = [
  "isbn_10", "isbn_13", "asin", "doi", "oclc", "lccn", "openlibrary",
  "calibre", "epub_uid", "publisher", "uri", "uuid", "other",
] as const;

export type BookIdentifierScheme = typeof bookIdentifierSchemes[number];

export interface BookIdentifierInput {
  scheme: BookIdentifierScheme;
  value: string;
}

export interface UpdateBookInput {
  title?: string;
  sortTitle?: string;
  subtitle?: string;
  description?: string;
  publisher?: string;
  language?: string;
  publishedYear?: number | null;
  publishedMonth?: number | null;
  publishedDay?: number | null;
  publishedDatePrecision?: "" | "year" | "month" | "day";
  authorIds?: string[];
  seriesId?: string | null;
  seriesIndex?: string | null;
  identifiers?: BookIdentifierInput[];
  catalogTagNames?: string[];
}

export interface BookPreview {
  id: string;
  title: string;
  coverUrl: string | null;
}

export interface LibraryAuthor {
  id: string;
  name: string;
  sortName: string;
  biography: string;
  bookCount: number;
  previewBooks?: BookPreview[];
}

export interface LibrarySeries {
  id: string;
  name: string;
  sortName: string;
  summary: string;
  bookCount: number;
  previewBooks?: BookPreview[];
}

export interface BookAuthorSummary {
  id: string;
  name: string;
}

export interface BookSeriesSummary {
  id: string;
  name: string;
  sortName: string;
  seriesIndex: string | null;
}

export interface CatalogTagSummary {
  id: string;
  name: string;
  slug: string;
}

export interface CatalogTag extends CatalogTagSummary {
  bookCount: number;
}

export interface CompactBook {
  id: string;
  title: string;
  sortTitle: string;
  subtitle: string;
  authors: BookAuthorSummary[];
  series: BookSeriesSummary | null;
  catalogTags: CatalogTagSummary[];
  language: string;
  publisher: string;
  publishedYear: number | null;
  publishedMonth: number | null;
  publishedDay: number | null;
  publishedDatePrecision: string;
  coverUrl: string | null;
  fileFormat: string;
}

export interface BookIdentifier {
  id: string;
  scheme: string;
  value: string;
}

export interface BookGroupSummary {
  id: string;
  name: string;
  description: string;
  isPublicGroup: boolean;
}

export interface BookFileDetail {
  format: string;
  fileSize: number | null;
  checksum: string | null;
  downloadUrl: string;
}

export interface BookDetail {
  id: string;
  title: string;
  sortTitle: string;
  subtitle: string;
  authors: BookAuthorSummary[];
  series: BookSeriesSummary | null;
  language: string;
  publisher: string;
  publishedYear: number | null;
  publishedMonth: number | null;
  publishedDay: number | null;
  publishedDatePrecision: string;
  coverUrl: string | null;
  description: string;
  identifiers: BookIdentifier[];
  catalogTags: CatalogTagSummary[];
  file: BookFileDetail | null;
  groups: BookGroupSummary[];
}

interface BookDetailResponse {
  id: string;
  title: string;
  sort_title: string;
  subtitle: string;
  authors: Array<{ id: string; name: string }>;
  series: { id: string; name: string; sort_name: string; series_index: string | null } | null;
  language: string;
  publisher: string;
  published_year: number | null;
  published_month: number | null;
  published_day: number | null;
  published_date_precision: string;
  cover_url: string | null;
  description: string;
  identifiers: Array<{ id: string; scheme: string; value: string }>;
  catalog_tags: Array<{ id: string; name: string; slug: string }>;
  file: { format: string; file_size: number | null; checksum: string | null; download_url: string } | null;
  groups: Array<{ id: string; name: string; description: string; is_public_group: boolean }>;
}

interface CatalogTagResponse {
  id: string;
  name: string;
  slug: string;
  book_count: number;
}

interface BookPreviewResponse {
  id: string;
  title: string;
  cover_url: string | null;
}

interface LibraryAuthorResponse {
  id: string;
  name: string;
  sort_name: string;
  biography: string;
  book_count: number;
  preview_books?: BookPreviewResponse[];
}

interface LibrarySeriesResponse {
  id: string;
  name: string;
  sort_name: string;
  summary: string;
  book_count: number;
  preview_books?: BookPreviewResponse[];
}

export async function listBooks(query: LibraryBooksQuery = {}, client: ApiClient = apiClient): Promise<Page<CompactBook>> {
  const parameters = new URLSearchParams();
  const search = query.q?.trim();
  if (search) parameters.set("q", search);
  if (query.tag) parameters.set("tag", query.tag);
  if (query.authorId) parameters.set("author", query.authorId);
  if (query.seriesId) parameters.set("series", query.seriesId);
  if (query.ordering) parameters.set("ordering", query.ordering);
  if (query.page) parameters.set("page", String(query.page));
  if (query.pageSize) parameters.set("page_size", String(query.pageSize));
  return toPage(
    await client.request<ApiPage<CompactBookResponse>>(withQuery("/api/v1/library/books/", parameters)),
    mapCompactBook,
  );
}

export async function searchLibraryBooks(
  query: LibraryBookSearchQuery,
  client: ApiClient = apiClient,
): Promise<Page<CompactBook>> {
  const parameters = new URLSearchParams({ q: query.q.trim() });
  if (query.excludeShelfId) parameters.set("exclude_shelf", query.excludeShelfId);
  if (query.excludeGroupId) parameters.set("exclude_group", query.excludeGroupId);
  if (query.ordering) parameters.set("ordering", query.ordering);
  if (query.page) parameters.set("page", String(query.page));
  if (query.pageSize) parameters.set("page_size", String(query.pageSize));
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

export async function listAuthors(query: LibraryAxisQuery = {}, client: ApiClient = apiClient): Promise<Page<LibraryAuthor>> {
  return listLibraryAxis("/api/v1/library/authors/", query, mapLibraryAuthor, client);
}

export async function listSeries(query: LibraryAxisQuery = {}, client: ApiClient = apiClient): Promise<Page<LibrarySeries>> {
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

function withQuery(path: string, parameters: URLSearchParams): string {
  const query = parameters.toString();
  return `${path}${query ? `?${query}` : ""}`;
}

async function listLibraryAxis<Response, Item>(
  path: string,
  query: LibraryAxisQuery,
  mapper: (response: Response) => Item,
  client: ApiClient,
): Promise<Page<Item>> {
  const parameters = new URLSearchParams();
  const search = query.q?.trim();
  if (search) parameters.set("q", search);
  if (query.tag) parameters.set("tag", query.tag);
  if (query.ordering) parameters.set("ordering", query.ordering);
  if (query.includePreviewBooks) parameters.set("include_preview_books", "true");
  if (query.previewLimit !== undefined) parameters.set("preview_limit", String(query.previewLimit));
  if (query.page) parameters.set("page", String(query.page));
  if (query.pageSize) parameters.set("page_size", String(query.pageSize));
  try {
    return toPage(await client.request<ApiPage<Response>>(withQuery(path, parameters)), mapper);
  } catch (error: unknown) {
    if (!(error instanceof ApiError) || !error.fields?.preview_limit) throw error;
    const { preview_limit: previewLimit, ...fields } = error.fields;
    throw new ApiError(error.message, error.status, {
      code: error.code,
      fields: { ...fields, previewLimit },
    });
  }
}

async function listAllLibraryAxis<Response, Item>(
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

async function mutateLibraryAxis<Response, Item>(
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

export function mapBookDetail(response: BookDetailResponse): BookDetail {
  return {
    id: response.id,
    title: response.title,
    sortTitle: response.sort_title,
    subtitle: response.subtitle,
    authors: response.authors.map(({ id, name }) => ({ id, name })),
    series: response.series ? {
      id: response.series.id,
      name: response.series.name,
      sortName: response.series.sort_name,
      seriesIndex: response.series.series_index,
    } : null,
    language: response.language,
    publisher: response.publisher,
    publishedYear: response.published_year,
    publishedMonth: response.published_month,
    publishedDay: response.published_day,
    publishedDatePrecision: response.published_date_precision,
    coverUrl: response.cover_url,
    description: response.description,
    identifiers: response.identifiers.map(({ id, scheme, value }) => ({ id, scheme, value })),
    catalogTags: response.catalog_tags.map(({ id, name, slug }) => ({ id, name, slug })),
    file: response.file ? {
      format: response.file.format,
      fileSize: response.file.file_size,
      checksum: response.file.checksum,
      downloadUrl: sameOriginUrl(response.file.download_url),
    } : null,
    groups: response.groups.map(({ id, name, description, is_public_group }) => ({
      id,
      name,
      description,
      isPublicGroup: is_public_group,
    })),
  };
}

function mapCatalogTag(response: CatalogTagResponse): CatalogTag {
  return { id: response.id, name: response.name, slug: response.slug, bookCount: response.book_count };
}

function mapBookPreview(response: BookPreviewResponse): BookPreview {
  return { id: response.id, title: response.title, coverUrl: response.cover_url };
}

export function mapLibraryAuthor(response: LibraryAuthorResponse): LibraryAuthor {
  return {
    id: response.id,
    name: response.name,
    sortName: response.sort_name,
    biography: response.biography,
    bookCount: response.book_count,
    ...(response.preview_books === undefined ? {} : { previewBooks: response.preview_books.map(mapBookPreview) }),
  };
}

export function mapLibrarySeries(response: LibrarySeriesResponse): LibrarySeries {
  return {
    id: response.id,
    name: response.name,
    sortName: response.sort_name,
    summary: response.summary,
    bookCount: response.book_count,
    ...(response.preview_books === undefined ? {} : { previewBooks: response.preview_books.map(mapBookPreview) }),
  };
}
