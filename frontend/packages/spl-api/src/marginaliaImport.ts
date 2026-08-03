import { apiClient, type ApiClient, type AttachmentApiClient, type AttachmentDownload } from "./client";
import type { MarginaliaSessionStatus } from "./marginalia";

export type MarginaliaImportUnmatchedReason = "not_found" | "ambiguous_match" | "book_inaccessible";

export interface MarginaliaImportWarning {
  code: string;
  message: string;
  candidateId?: string;
}

export interface MarginaliaImportPreviewSession {
  candidateId: string;
  sourceReadingSessionId: string;
  name: string;
  notes: string;
  sourceStatus: MarginaliaSessionStatus;
  willImportAsStatus: "closed";
  startedAt: string;
  closedAt: string | null;
  annotationCount: number;
  willImport: boolean;
  possibleDuplicate: boolean;
  warnings: MarginaliaImportWarning[];
}

export type MarginaliaImportBookMatch =
  | { status: "matched"; bookId: string }
  | { status: "unmatched"; reason: MarginaliaImportUnmatchedReason };

export interface MarginaliaImportPreviewBook {
  candidateId: string;
  fileHash: string;
  title: string;
  authors: string[];
  match: MarginaliaImportBookMatch;
  readingSessions: MarginaliaImportPreviewSession[];
}

export interface MarginaliaImportPreview {
  importToken: string;
  includeEmptySessions: boolean;
  canApply: boolean;
  summary: {
    bookCount: number;
    readingSessionCount: number;
    annotationCount: number;
  };
  matchedBookCount: number;
  unmatchedBookCount: number;
  unmatchedReadingSessionCount: number;
  unmatchedDownloadableReadingSessionCount: number;
  warnings: MarginaliaImportWarning[];
  books: MarginaliaImportPreviewBook[];
}

export interface MarginaliaImportApplyInput {
  importToken: string;
  readingSessions: Array<{
    candidateId: string;
    name?: string;
    notes?: string;
  }>;
}

export interface MarginaliaImportedSessionResult {
  candidateId: string;
  readingSessionId: string;
  status: "closed";
  name: string;
  annotationCount: number;
}

export interface MarginaliaImportApplyResult {
  importedReadingSessionCount: number;
  importedAnnotationCount: number;
  unmatchedReadingSessionCount: number;
  unmatchedDownloadableReadingSessionCount: number;
  unmatchedDownloadAvailable: boolean;
  unmatchedBooks: Array<{
    candidateId: string;
    title: string;
    reason: MarginaliaImportUnmatchedReason;
  }>;
  readingSessions: MarginaliaImportedSessionResult[];
  warnings: MarginaliaImportWarning[];
}

interface ImportWarningResponse {
  code: string;
  message: string;
  candidate_id?: string;
}

interface ImportPreviewResponse {
  import_token: string;
  include_empty_sessions: boolean;
  can_apply: boolean;
  summary: { book_count: number; reading_session_count: number; annotation_count: number };
  matched_book_count: number;
  unmatched_book_count: number;
  unmatched_reading_session_count: number;
  unmatched_downloadable_reading_session_count: number;
  warnings: ImportWarningResponse[];
  books: Array<{
    candidate_id: string;
    file_hash: string;
    title: string;
    authors: string[];
    match: { status: "matched"; book_id: string } | { status: "unmatched"; reason: MarginaliaImportUnmatchedReason };
    reading_sessions: Array<{
      candidate_id: string;
      source_reading_session_id: string;
      name: string;
      notes: string;
      source_status: MarginaliaSessionStatus;
      will_import_as_status: "closed";
      started_at: string;
      closed_at: string | null;
      annotation_count: number;
      will_import: boolean;
      possible_duplicate: boolean;
    }>;
  }>;
}

interface ImportApplyResponse {
  imported_reading_session_count: number;
  imported_annotation_count: number;
  unmatched_reading_session_count: number;
  unmatched_downloadable_reading_session_count: number;
  unmatched_download_available: boolean;
  unmatched_books: Array<{
    candidate_id: string;
    title: string;
    reason: MarginaliaImportUnmatchedReason;
  }>;
  reading_sessions: Array<{
    candidate_id: string;
    reading_session_id: string;
    status: "closed";
    name: string;
    annotation_count: number;
  }>;
  warnings: ImportWarningResponse[];
}

export async function previewMarginaliaImport(
  file: File,
  input: { includeEmptySessions?: boolean } = {},
  client: ApiClient = apiClient,
): Promise<MarginaliaImportPreview> {
  const body = new FormData();
  body.append("file", file);
  body.append("include_empty_sessions", String(input.includeEmptySessions ?? false));
  const response = await client.request<ImportPreviewResponse>(
    "/api/v1/marginalia/import/preview/",
    { method: "POST", body },
  );
  const warnings = response.warnings.map(mapImportWarning);
  return {
    importToken: response.import_token,
    includeEmptySessions: response.include_empty_sessions,
    canApply: response.can_apply,
    summary: {
      bookCount: response.summary.book_count,
      readingSessionCount: response.summary.reading_session_count,
      annotationCount: response.summary.annotation_count,
    },
    matchedBookCount: response.matched_book_count,
    unmatchedBookCount: response.unmatched_book_count,
    unmatchedReadingSessionCount: response.unmatched_reading_session_count,
    unmatchedDownloadableReadingSessionCount: response.unmatched_downloadable_reading_session_count,
    warnings,
    books: response.books.map((book) => ({
      candidateId: book.candidate_id,
      fileHash: book.file_hash,
      title: book.title,
      authors: [...book.authors],
      match: book.match.status === "matched"
        ? { status: "matched", bookId: book.match.book_id }
        : { status: "unmatched", reason: book.match.reason },
      readingSessions: book.reading_sessions.map((session) => ({
        candidateId: session.candidate_id,
        sourceReadingSessionId: session.source_reading_session_id,
        name: session.name,
        notes: session.notes,
        sourceStatus: session.source_status,
        willImportAsStatus: session.will_import_as_status,
        startedAt: session.started_at,
        closedAt: session.closed_at,
        annotationCount: session.annotation_count,
        willImport: session.will_import,
        possibleDuplicate: session.possible_duplicate,
        warnings: warnings.filter((warning) => warning.candidateId === session.candidate_id),
      })),
    })),
  };
}

export async function applyMarginaliaImport(
  input: MarginaliaImportApplyInput,
  client: ApiClient = apiClient,
): Promise<MarginaliaImportApplyResult> {
  const response = await client.request<ImportApplyResponse>(
    "/api/v1/marginalia/import/apply/",
    jsonRequest("POST", {
      import_token: input.importToken,
      reading_sessions: input.readingSessions.map((session) => ({
        candidate_id: session.candidateId,
        ...(session.name !== undefined ? { name: session.name } : {}),
        ...(session.notes !== undefined ? { notes: session.notes } : {}),
      })),
    }),
  );
  return {
    importedReadingSessionCount: response.imported_reading_session_count,
    importedAnnotationCount: response.imported_annotation_count,
    unmatchedReadingSessionCount: response.unmatched_reading_session_count,
    unmatchedDownloadableReadingSessionCount: response.unmatched_downloadable_reading_session_count,
    unmatchedDownloadAvailable: response.unmatched_download_available,
    unmatchedBooks: response.unmatched_books.map((book) => ({
      candidateId: book.candidate_id,
      title: book.title,
      reason: book.reason,
    })),
    readingSessions: response.reading_sessions.map((session) => ({
      candidateId: session.candidate_id,
      readingSessionId: session.reading_session_id,
      status: session.status,
      name: session.name,
      annotationCount: session.annotation_count,
    })),
    warnings: response.warnings.map(mapImportWarning),
  };
}

export function downloadUnmatchedMarginaliaImport(
  importToken: string,
  client: AttachmentApiClient = apiClient,
): Promise<AttachmentDownload> {
  const parameters = new URLSearchParams({ import_token: importToken });
  return client.requestAttachment(
    `/api/v1/marginalia/import/unmatched/?${parameters.toString()}`,
    undefined,
    "secondpass-marginalia-sessions.zip",
  );
}

function mapImportWarning(item: ImportWarningResponse): MarginaliaImportWarning {
  return {
    code: item.code,
    message: item.message,
    ...(item.candidate_id !== undefined ? { candidateId: item.candidate_id } : {}),
  };
}

function jsonRequest(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}
