import { sameOriginUrl } from "../sameOriginUrl";
import type { BookDetail, BookPreview, CatalogTag, LibraryAuthor, LibrarySeries } from "./types";
import type { BookDetailResponse, BookPreviewResponse, CatalogTagResponse, LibraryAuthorResponse, LibrarySeriesResponse } from "./wire";

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

export function mapCatalogTag(response: CatalogTagResponse): CatalogTag {
  return { id: response.id, name: response.name, slug: response.slug, bookCount: response.book_count };
}

export function mapBookPreview(response: BookPreviewResponse): BookPreview {
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

