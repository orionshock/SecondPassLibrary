import { apiClient, type ApiClient } from "./client";

export type ImportItemStatus = "imported" | "duplicate" | "conflict" | "failed" | "skipped";

export interface LibraryImportCounts {
  imported: number;
  duplicate: number;
  conflict: number;
  failed: number;
  skipped: number;
}

export interface LibraryImportItem {
  status: ImportItemStatus;
  sourceLabel: string;
  safeMessage: string;
  errorCategory: string;
  bookId?: string;
  title?: string;
  authors?: string[];
  series?: string;
  seriesIndex?: string;
}

export interface LibraryImportResult {
  sourceType: string;
  sourceLabel: string;
  counts: LibraryImportCounts;
  items: LibraryImportItem[];
}

interface LibraryImportResponse {
  source_type: string;
  source_label: string;
  counts: LibraryImportCounts;
  items: Array<{
    status: ImportItemStatus;
    source_label: string;
    safe_message: string;
    error_category: string;
    book_id?: string;
    title?: string;
    authors?: string[];
    series?: string;
    series_index?: string;
  }>;
}

export async function uploadLibraryImport(file: File, client: ApiClient = apiClient): Promise<LibraryImportResult> {
  const body = new FormData();
  body.append("file", file);
  const response = await client.request<LibraryImportResponse>("/api/v1/library/imports/", { method: "POST", body });
  return {
    sourceType: response.source_type,
    sourceLabel: response.source_label,
    counts: { ...response.counts },
    items: response.items.map((item) => ({
      status: item.status,
      sourceLabel: item.source_label,
      safeMessage: item.safe_message,
      errorCategory: item.error_category,
      ...(item.book_id ? { bookId: item.book_id } : {}),
      ...(item.title ? { title: item.title } : {}),
      ...(item.authors ? { authors: [...item.authors] } : {}),
      ...(item.series ? { series: item.series } : {}),
      ...(item.series_index ? { seriesIndex: item.series_index } : {}),
    })),
  };
}
