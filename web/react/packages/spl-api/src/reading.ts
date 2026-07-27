import { apiClient, type ApiClient, type AttachmentApiClient, type AttachmentDownload } from "./client";
import { toPage, type ApiPage, type Page } from "./pagination";
import { sameOriginUrl } from "./urls";

export type ReadingSessionStatus = "active" | "completed" | "archived";

interface ReadingSessionSummaryResponse {
  id: string;
  book_id: string;
  name: string;
  status: ReadingSessionStatus;
  is_active: boolean;
  started_at: string;
  completed_at: string | null;
  updated_at: string;
  notes: string;
  progression: number | null;
  annotation_count: number;
  can_open: boolean;
  book: {
    id: string | null;
    title: string;
    cover_url: string | null;
  };
}

export interface ReadingSessionSummary {
  id: string;
  bookId: string;
  name: string;
  status: ReadingSessionStatus;
  isActive: boolean;
  startedAt: string;
  completedAt: string | null;
  updatedAt: string;
  notes: string;
  progression: number | null;
  annotationCount: number;
  canOpen: boolean;
  book: {
    id: string | null;
    title: string;
    coverUrl: string | null;
    unavailable: boolean;
  };
}

export interface ReadingSessionsQuery {
  q?: string;
  isActive?: boolean;
  status?: ReadingSessionStatus;
  page?: number;
  pageSize?: number;
}

interface ReadingSessionDetailResponse extends ReadingSessionSummaryResponse {
  created_at: string;
  book: ReadingSessionSummaryResponse["book"] & {
    authors: Array<{ id: string; name: string }>;
    series: { id: string; name: string } | null;
    series_index: string | null;
  };
}

export interface ReadingSessionDetail {
  id: string;
  name: string;
  status: ReadingSessionStatus;
  isActive: boolean;
  startedAt: string;
  completedAt: string | null;
  createdAt: string;
  updatedAt: string;
  notes: string;
  progression: number | null;
  annotationCount: number;
  canOpen: boolean;
  book: {
    id: string | null;
    title: string;
    authors: Array<{ id: string; name: string }>;
    series: { id: string; name: string } | null;
    seriesIndex: string | null;
    coverUrl: string | null;
    unavailable: boolean;
  };
}

interface ReadingProgressResponse {
  session: string;
  progression: number | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ReadingProgress {
  sessionId: string;
  progression: number | null;
  createdAt: string | null;
  updatedAt: string | null;
}

export type ReadingAnnotationKind = "highlight" | "bookmark";
export type ReadingAnnotationCategory = "bookmark" | "highlight" | "highlightWithNote";
export type ReadingAnnotationOrdering = "created" | "-created" | "modified" | "-modified";

interface ReadingAnnotationResponse {
  id: string;
  kind: ReadingAnnotationKind;
  highlight_text: string;
  highlight_color: string;
  comment_text: string;
  has_comment: boolean;
  created_at: string;
  updated_at: string;
}

export interface ReadingAnnotation {
  id: string;
  kind: ReadingAnnotationKind;
  highlightText: string;
  highlightColor: string;
  commentText: string;
  hasComment: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface ReadingAnnotationsQuery {
  sessionId: string;
  kind?: ReadingAnnotationKind;
  categories?: readonly ReadingAnnotationCategory[];
  ordering?: ReadingAnnotationOrdering;
  page?: number;
  pageSize?: number;
}

export interface ReadingExportSessionSelection {
  sessionId: string;
  bookId: string;
}

export interface ReadingExportSelection {
  sessions: readonly ReadingExportSessionSelection[];
}

export interface ReadingImportCounts {
  books: number;
  sessions: number;
  annotations: number;
}

export interface ReadingImportSessionPreview {
  exportSessionId: string;
  name: string;
  notes: string;
  status: string;
  startedAt: string | null;
  completedAt: string | null;
  annotationCount: number;
  bookmarkCount: number;
  highlightCount: number;
  commentedHighlightCount: number;
  willImport: boolean;
  needsReader: boolean;
  activeWillImportAsHistorical: boolean;
  possibleDuplicate: boolean;
  warning: string;
}

export interface ReadingImportBookPreview {
  title: string;
  authors: string[];
  selectionReference: { source: string; fileHash: string; title: string };
  sessionCount: number;
  annotationCount: number;
  matchStatus: "matched" | "unmatched";
  matchedBookTitle: string | null;
  coverUrl: string | null;
  willImport: boolean;
  warning: string;
  sessions: ReadingImportSessionPreview[];
}

export interface ReadingImportPreview {
  importToken: string;
  valid: boolean;
  canApply: boolean;
  summary: ReadingImportCounts;
  books: ReadingImportBookPreview[];
  warnings: string[];
  unmatchedEntries: number;
  unmatchedDownloadAvailable: boolean;
}

export interface ReadingImportSelectedSession {
  exportSessionId: string;
  name?: string;
  notes?: string;
}

export interface ReadingImportSelectedBook {
  selectionReference: { source: string; fileHash: string; title: string };
  sessions: ReadingImportSelectedSession[];
}

export interface ReadingImportApplyInput {
  importToken: string;
  books: ReadingImportSelectedBook[];
}

export interface ReadingImportResult {
  applied: boolean;
  summary: {
    booksMatched: number;
    booksSkipped: number;
    sessionsCreated: number;
    annotationsCreated: number;
    bookmarksCreated: number;
    highlightsCreated: number;
    commentedHighlightsCreated: number;
  };
  warnings: string[];
}

interface ReadingImportPreviewResponse {
  valid: boolean;
  import_token: string;
  can_apply: boolean;
  summary: { books: number; sessions: number; annotations: number };
  warnings: string[];
  unmatched_entries: number;
  unmatched_download_url?: string;
  books: Array<{
    title: string;
    authors: string[];
    source: string;
    file_hash: string;
    session_count: number;
    annotation_count: number;
    match: { status: "matched" | "unmatched"; book_title: string | null };
    cover_url: string;
    will_import: boolean;
    warning: string;
    sessions: Array<{
      export_session_id: string;
      name: string;
      notes: string;
      status: string;
      started_at: string | null;
      completed_at: string | null;
      annotation_count: number;
      bookmark_count: number;
      highlight_count: number;
      commented_highlight_count: number;
      will_import: boolean;
      needs_reader: boolean;
      active_will_import_as_historical: boolean;
      possible_duplicate: boolean;
      warning: string;
    }>;
  }>;
}

interface ReadingImportResultResponse {
  applied: boolean;
  summary: {
    books_matched: number;
    books_skipped: number;
    sessions_created: number;
    annotations_created: number;
    bookmarks_created: number;
    highlights_created: number;
    commented_highlights_created: number;
  };
  warnings: string[];
}

export async function previewReadingImport(file: File, client: ApiClient = apiClient): Promise<ReadingImportPreview> {
  const body = new FormData();
  body.append("file", file);
  const response = await client.request<ReadingImportPreviewResponse>("/api/v1/reading/import/preview/", { method: "POST", body });
  return {
    importToken: response.import_token,
    valid: response.valid,
    canApply: response.can_apply,
    summary: { ...response.summary },
    warnings: [...response.warnings],
    unmatchedEntries: response.unmatched_entries,
    unmatchedDownloadAvailable: Boolean(response.unmatched_download_url),
    books: response.books.map((book) => ({
      title: book.title,
      authors: [...book.authors],
      selectionReference: { source: book.source, fileHash: book.file_hash, title: book.title },
      sessionCount: book.session_count,
      annotationCount: book.annotation_count,
      matchStatus: book.match.status,
      matchedBookTitle: book.match.book_title,
      coverUrl: book.cover_url ? sameOriginUrl(book.cover_url) : null,
      willImport: book.will_import,
      warning: book.warning,
      sessions: book.sessions.map((session) => ({
        exportSessionId: session.export_session_id,
        name: session.name,
        notes: session.notes,
        status: session.status,
        startedAt: session.started_at,
        completedAt: session.completed_at,
        annotationCount: session.annotation_count,
        bookmarkCount: session.bookmark_count,
        highlightCount: session.highlight_count,
        commentedHighlightCount: session.commented_highlight_count,
        willImport: session.will_import,
        needsReader: session.needs_reader,
        activeWillImportAsHistorical: session.active_will_import_as_historical,
        possibleDuplicate: session.possible_duplicate,
        warning: session.warning,
      })),
    })),
  };
}

export async function applyReadingImport(input: ReadingImportApplyInput, client: ApiClient = apiClient): Promise<ReadingImportResult> {
  const selection = {
    books: input.books.map((book) => ({
      ...(book.selectionReference.source
        ? { source: book.selectionReference.source }
        : book.selectionReference.fileHash
          ? { file_hash: book.selectionReference.fileHash }
          : { title: book.selectionReference.title }),
      sessions: book.sessions.map((session) => ({
        export_session_id: session.exportSessionId,
        selected: true,
        ...(session.name !== undefined ? { name: session.name } : {}),
        ...(session.notes !== undefined ? { notes: session.notes } : {}),
      })),
    })),
  };
  const body = new FormData();
  body.append("import_token", input.importToken);
  body.append("selection", JSON.stringify(selection));
  const response = await client.request<ReadingImportResultResponse>("/api/v1/reading/import/apply/", { method: "POST", body });
  return {
    applied: response.applied,
    summary: {
      booksMatched: response.summary.books_matched,
      booksSkipped: response.summary.books_skipped,
      sessionsCreated: response.summary.sessions_created,
      annotationsCreated: response.summary.annotations_created,
      bookmarksCreated: response.summary.bookmarks_created,
      highlightsCreated: response.summary.highlights_created,
      commentedHighlightsCreated: response.summary.commented_highlights_created,
    },
    warnings: [...response.warnings],
  };
}

export async function listReadingSessions(
  query: ReadingSessionsQuery = {},
  client: ApiClient = apiClient,
): Promise<Page<ReadingSessionSummary>> {
  const parameters = new URLSearchParams();
  if (query.q !== undefined) parameters.set("q", query.q);
  if (query.isActive !== undefined) parameters.set("is_active", String(query.isActive));
  if (query.status !== undefined) parameters.set("status", query.status);
  if (query.page !== undefined) parameters.set("page", String(query.page));
  if (query.pageSize !== undefined) parameters.set("page_size", String(query.pageSize));
  const suffix = parameters.size ? `?${parameters.toString()}` : "";
  const response = await client.request<ApiPage<ReadingSessionSummaryResponse>>(
    `/api/v1/reading/sessions/${suffix}`,
  );
  return toPage(response, mapReadingSessionSummary);
}

export async function getReadingSession(sessionId: string, client: ApiClient = apiClient): Promise<ReadingSessionDetail> {
  const item = await client.request<ReadingSessionDetailResponse>(`/api/v1/reading/sessions/${encodeURIComponent(sessionId)}/`);
  return {
    id: item.id,
    name: item.name,
    status: item.status,
    isActive: item.is_active,
    startedAt: item.started_at,
    completedAt: item.completed_at,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
    notes: item.notes,
    progression: item.progression,
    annotationCount: item.annotation_count,
    canOpen: item.can_open,
    book: {
      id: item.can_open ? item.book.id : null,
      title: item.book.title,
      authors: item.book.authors.map((author) => ({ ...author })),
      series: item.book.series ? { ...item.book.series } : null,
      seriesIndex: item.book.series_index,
      coverUrl: item.book.cover_url === null ? null : sameOriginUrl(item.book.cover_url),
      unavailable: !item.can_open,
    },
  };
}

export async function getReadingProgress(sessionId: string, client: ApiClient = apiClient): Promise<ReadingProgress> {
  const item = await client.request<ReadingProgressResponse>(`/api/v1/reading/sessions/${encodeURIComponent(sessionId)}/progress/`);
  return {
    sessionId: item.session,
    progression: item.progression,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  };
}

export async function listReadingAnnotations(query: ReadingAnnotationsQuery, client: ApiClient = apiClient): Promise<Page<ReadingAnnotation>> {
  const parameters = new URLSearchParams({ session_id: query.sessionId });
  if (query.kind !== undefined) parameters.set("kind", query.kind);
  for (const category of query.categories ?? []) {
    parameters.append("category", category === "highlightWithNote" ? "highlight_with_note" : category);
  }
  if (query.ordering !== undefined) parameters.set("ordering", query.ordering);
  if (query.page !== undefined) parameters.set("page", String(query.page));
  if (query.pageSize !== undefined) parameters.set("page_size", String(query.pageSize));
  const response = await client.request<ApiPage<ReadingAnnotationResponse>>(`/api/v1/reading/annotations/?${parameters.toString()}`);
  return toPage(response, (item) => ({
    id: item.id,
    kind: item.kind,
    highlightText: item.highlight_text,
    highlightColor: item.highlight_color,
    commentText: item.comment_text,
    hasComment: item.has_comment,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  }));
}

export function downloadCompleteReadingExport(client: AttachmentApiClient = apiClient): Promise<AttachmentDownload> {
  return client.requestAttachment("/api/v1/reading/export/", undefined, "second-pass-marginalia.json");
}

export function downloadSelectedReadingExport(selection: ReadingExportSelection, client: AttachmentApiClient = apiClient): Promise<AttachmentDownload> {
  const sessionsByBook = new Map<string, string[]>();
  for (const selected of selection.sessions) {
    const sessions = sessionsByBook.get(selected.bookId) ?? [];
    if (!sessions.includes(selected.sessionId)) sessions.push(selected.sessionId);
    sessionsByBook.set(selected.bookId, sessions);
  }
  return client.requestAttachment("/api/v1/reading/export/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      books: [...sessionsByBook].map(([bookId, sessions]) => ({ book_id: bookId, sessions })),
    }),
  }, "second-pass-marginalia.json");
}

function mapReadingSessionSummary(item: ReadingSessionSummaryResponse): ReadingSessionSummary {
  return {
    id: item.id,
    bookId: item.book_id,
    name: item.name,
    status: item.status,
    isActive: item.is_active,
    startedAt: item.started_at,
    completedAt: item.completed_at,
    updatedAt: item.updated_at,
    notes: item.notes,
    progression: item.progression,
    annotationCount: item.annotation_count,
    canOpen: item.can_open,
    book: {
      id: item.book.id,
      title: item.book.title,
      coverUrl: item.book.cover_url === null ? null : sameOriginUrl(item.book.cover_url),
      unavailable: !item.can_open,
    },
  };
}

interface RecentReadingSessionsResponse {
  count: number;
  results: RecentReadingSessionResponse[];
}

interface RecentReadingSessionResponse {
  last_activity_at: string;
  session: {
    id: string;
    name: string;
    status: string;
    is_active: boolean;
    progression: number | null;
  };
  book: {
    id: string;
    title: string;
    cover_url: string | null;
  };
}

export interface RecentReadingSession {
  lastActivityAt: string;
  session: {
    id: string;
    name: string;
    status: string;
    isActive: boolean;
    progression: number | null;
  };
  book: {
    id: string;
    title: string;
    coverUrl: string | null;
  };
}

export async function listRecentReadingSessions(
  query: { limit?: number } = {},
  client: ApiClient = apiClient,
): Promise<RecentReadingSession[]> {
  const parameters = new URLSearchParams();
  if (query.limit !== undefined) parameters.set("limit", String(query.limit));
  const suffix = parameters.size ? `?${parameters.toString()}` : "";
  const response = await client.request<RecentReadingSessionsResponse>(
    `/api/v1/reading/sessions/recent/${suffix}`,
  );
  return response.results.map((item) => ({
    lastActivityAt: item.last_activity_at,
    session: {
      id: item.session.id,
      name: item.session.name,
      status: item.session.status,
      isActive: item.session.is_active,
      progression: item.session.progression,
    },
    book: {
      id: item.book.id,
      title: item.book.title,
      coverUrl: item.book.cover_url === null ? null : sameOriginUrl(item.book.cover_url),
    },
  }));
}
