import type { CompactBook } from "./types";

/** @internal Canonical wire shape for every compact Book projection. */
export interface CompactBookResponse {
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

/** @internal Maps the compact wire projection to the stable app-facing contract. */
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

