export interface BookDetailResponse {
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

export interface CatalogTagResponse {
  id: string;
  name: string;
  slug: string;
  book_count: number;
}

export interface CatalogResultPageResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  catalog_tags: CatalogTagResponse[];
  results: T[];
}

export interface BookPreviewResponse {
  id: string;
  title: string;
  cover_url: string | null;
}

export interface LibraryAuthorResponse {
  id: string;
  name: string;
  sort_name: string;
  biography: string;
  book_count: number;
  preview_books?: BookPreviewResponse[];
}

export interface LibrarySeriesResponse {
  id: string;
  name: string;
  sort_name: string;
  summary: string;
  book_count: number;
  preview_books?: BookPreviewResponse[];
}
