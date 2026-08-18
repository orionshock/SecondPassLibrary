export type BookOrdering =
  | "title" | "-title"
  | "author" | "-author"
  | "series" | "-series"
  | "series_index" | "-series_index"
  | "publisher" | "-publisher";

export type LibrarySearchOrdering =
  | "title" | "-title"
  | "author" | "-author"
  | "series" | "-series";

export interface LibraryBooksQuery {
  q?: string;
  tag?: string;
  authorId?: string;
  seriesId?: string;
  publisher?: string;
  excludeGroupId?: string;
  ordering?: BookOrdering;
  page?: number;
  pageSize?: number;
}

export interface LibraryBookSearchQuery {
  q: string;
  excludeShelfId?: string;
  excludeGroupId?: string;
  ordering?: LibrarySearchOrdering;
  page?: number;
  pageSize?: number;
}

export type LibraryAxisOrdering = "name" | "-name" | "book_count" | "-book_count";

export interface LibraryAxisQuery {
  q?: string;
  excludeId?: string;
  tag?: string;
  ordering?: LibraryAxisOrdering;
  includePreviewBooks?: boolean;
  previewLimit?: number;
  page?: number;
  pageSize?: number;
}

export interface LibraryTagQuery {
  q?: string;
  ordering?: LibraryAxisOrdering;
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
