import { apiClient, type ApiClient } from "./client";
import { toPage, type ApiPage, type Page } from "./pagination";

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

export type LibraryAxisOrdering = "name" | "-name" | "book_count" | "-book_count";

export interface LibraryAxisQuery {
  q?: string;
  tag?: string;
  ordering?: LibraryAxisOrdering;
  includePreviewBooks?: boolean;
  page?: number;
  pageSize?: number;
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

interface CompactBookResponse {
  id: string;
  title: string;
  sort_title: string;
  subtitle: string;
  authors: Array<{ id: string; name: string }>;
  series: { id: string; name: string; sort_name: string; series_index: string | null } | null;
  catalog_tags: Array<{ id: string; name: string; slug: string }>;
  language: string;
  publisher: string;
  published_year: number | null;
  published_month: number | null;
  published_day: number | null;
  published_date_precision: string;
  cover_url: string | null;
  file_format: string;
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

export async function listAuthors(query: LibraryAxisQuery = {}, client: ApiClient = apiClient): Promise<Page<LibraryAuthor>> {
  return listLibraryAxis("/api/v1/library/authors/", query, mapLibraryAuthor, client);
}

export async function listSeries(query: LibraryAxisQuery = {}, client: ApiClient = apiClient): Promise<Page<LibrarySeries>> {
  return listLibraryAxis("/api/v1/library/series/", query, mapLibrarySeries, client);
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
  const tags: CatalogTag[] = [];
  let path: string | null = "/api/v1/library/tags/?ordering=name&page_size=200";
  while (path) {
    const page: ApiPage<CatalogTagResponse> = await client.request<ApiPage<CatalogTagResponse>>(path);
    tags.push(...page.results.map(mapCatalogTag));
    path = page.next;
  }
  return tags;
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
  if (query.page) parameters.set("page", String(query.page));
  if (query.pageSize) parameters.set("page_size", String(query.pageSize));
  return toPage(await client.request<ApiPage<Response>>(withQuery(path, parameters)), mapper);
}

export function mapCompactBook(response: CompactBookResponse): CompactBook {
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
    catalogTags: response.catalog_tags.map(({ id, name, slug }) => ({ id, name, slug })),
    language: response.language,
    publisher: response.publisher,
    publishedYear: response.published_year,
    publishedMonth: response.published_month,
    publishedDay: response.published_day,
    publishedDatePrecision: response.published_date_precision,
    coverUrl: response.cover_url,
    fileFormat: response.file_format,
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
