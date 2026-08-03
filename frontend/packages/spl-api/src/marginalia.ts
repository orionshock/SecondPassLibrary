import { apiClient, type ApiClient, type AttachmentApiClient, type AttachmentDownload } from "./client";
import { ApiError, apiErrorFromPayload } from "./errors";
import { toPage, type ApiPage, type Page } from "./pagination";
import { sameOriginUrl } from "./urls";

export type MarginaliaSessionStatus = "active" | "closed";
export type MarginaliaHighlightColor = "yellow" | "green" | "blue" | "pink" | "purple" | "orange";

export interface MarginaliaAuthor {
  id: string;
  name: string;
}

export interface MarginaliaSeries {
  id: string;
  name: string;
  seriesIndex: string | null;
}

export interface MarginaliaBookSummary {
  id: string;
  title: string;
  authors: MarginaliaAuthor[];
  series: MarginaliaSeries | null;
  coverUrl: string | null;
  canOpen: boolean;
  sessionCount: number;
  activeSessionCount: number;
  lastActivityAt: string;
}

export interface MarginaliaBookReference {
  id: string;
  title: string;
  coverUrl: string | null;
  canOpen: boolean;
}

export interface MarginaliaProgress {
  cfi: string;
  locationLabel: string;
  updatedAt: string;
}

export interface MarginaliaSessionSummary {
  id: string;
  name: string;
  notes: string;
  status: MarginaliaSessionStatus;
  startedAt: string;
  closedAt: string | null;
  updatedAt: string;
  lastActivityAt: string;
  annotationCount: number;
}

export interface MarginaliaSessionListItem extends MarginaliaSessionSummary {
  book: MarginaliaBookReference;
}

export interface RecentMarginaliaSession {
  id: string;
  name: string;
  status: MarginaliaSessionStatus;
  lastActivityAt: string;
  book: MarginaliaBookReference;
  progress: MarginaliaProgress | null;
}

export interface MarginaliaSessionDetail extends MarginaliaSessionSummary {
  progress: MarginaliaProgress | null;
}

export interface MarginaliaSessionEnvelope {
  book: MarginaliaBookSummary;
  session: MarginaliaSessionDetail;
}

export interface MarginaliaBookSessionsPage extends Page<MarginaliaSessionSummary> {
  book: MarginaliaBookSummary;
}

export interface MarginaliaLocation {
  cfi: string;
  locationLabel: string;
}

interface MarginaliaAnnotationBase {
  id: string;
  clientId: string;
  location: MarginaliaLocation;
  createdAt: string;
  updatedAt: string;
}

export interface MarginaliaHighlight extends MarginaliaAnnotationBase {
  kind: "highlight";
  body: {
    text: string;
    prefix: string;
    suffix: string;
    color: MarginaliaHighlightColor;
    note: string;
  };
}

export interface MarginaliaBookmark extends MarginaliaAnnotationBase {
  kind: "bookmark";
}

export type MarginaliaAnnotation = MarginaliaHighlight | MarginaliaBookmark;

export interface MarginaliaPageQuery {
  q?: string;
  page?: number;
  pageSize?: number;
}

export interface MarginaliaSessionsQuery extends MarginaliaPageQuery {
  status?: MarginaliaSessionStatus;
  hasAnnotations?: boolean;
}

export interface CompleteMarginaliaExportInput {
  includeEmptySessions?: boolean;
}

export interface SelectedMarginaliaExportInput extends CompleteMarginaliaExportInput {
  readingSessionIds: string[];
}

export type MarginaliaExportMode = "full" | "selected";
export type MarginaliaExportLimitKind =
  | "selected_sessions"
  | "full_sessions"
  | "annotations"
  | "estimated_archive_bytes"
  | "archive_bytes";

export class MarginaliaExportTooLargeError extends ApiError {
  readonly guidance: string;
  readonly exportMode: MarginaliaExportMode;
  readonly limitKind: MarginaliaExportLimitKind;
  readonly maximum: number;

  constructor(input: {
    message: string;
    guidance: string;
    exportMode: MarginaliaExportMode;
    limitKind: MarginaliaExportLimitKind;
    maximum: number;
  }) {
    super(input.message, 413, { code: "EXPORT_TOO_LARGE" });
    this.name = "MarginaliaExportTooLargeError";
    this.guidance = input.guidance;
    this.exportMode = input.exportMode;
    this.limitKind = input.limitKind;
    this.maximum = input.maximum;
  }
}

export interface RecentMarginaliaSessionsQuery {
  limit?: number;
  includeClosed?: boolean;
}

export interface MarginaliaSessionMetadataInput {
  name?: string;
  notes?: string;
}

export type MarginaliaSessionCloseInput = MarginaliaSessionMetadataInput;

interface BookSummaryResponse {
  id: string;
  title: string;
  authors: Array<{ id: string; name: string }>;
  series: { id: string; name: string; series_index: string | null } | null;
  cover_url: string | null;
  can_open: boolean;
  session_count: number;
  active_session_count: number;
  last_activity_at: string;
}

interface BookReferenceResponse {
  id: string;
  title: string;
  cover_url: string | null;
  can_open: boolean;
}

interface ProgressResponse {
  cfi: string;
  location_label: string;
  updated_at: string;
}

interface SessionSummaryResponse {
  id: string;
  name: string;
  notes: string;
  status: MarginaliaSessionStatus;
  started_at: string;
  closed_at: string | null;
  updated_at: string;
  last_activity_at: string;
  annotation_count: number;
}

interface GlobalSessionSummaryResponse extends SessionSummaryResponse {
  book: BookReferenceResponse;
}

interface RecentSessionResponse {
  id: string;
  name: string;
  status: MarginaliaSessionStatus;
  last_activity_at: string;
  book: BookReferenceResponse;
  progress: ProgressResponse | null;
}

interface RecentSessionsResponse {
  results: RecentSessionResponse[];
}

interface SessionDetailResponse extends SessionSummaryResponse {
  progress: ProgressResponse | null;
}

interface SessionEnvelopeResponse {
  context: { book: BookSummaryResponse };
  session: SessionDetailResponse;
}

interface BookSessionsPageResponse extends ApiPage<SessionSummaryResponse> {
  context: { book: BookSummaryResponse };
}

interface AnnotationLocationResponse {
  cfi: string;
  location_label: string;
}

interface AnnotationBaseResponse {
  id: string;
  client_id: string;
  location: AnnotationLocationResponse;
  created_at: string;
  updated_at: string;
}

interface HighlightResponse extends AnnotationBaseResponse {
  kind: "highlight";
  body: {
    text: string;
    prefix: string;
    suffix: string;
    color: MarginaliaHighlightColor;
    note: string;
  };
}

interface BookmarkResponse extends AnnotationBaseResponse {
  kind: "bookmark";
}

type AnnotationResponse = HighlightResponse | BookmarkResponse;

interface AnnotationCollectionResponse {
  annotations: AnnotationResponse[];
}

export async function listMarginaliaBooks(
  query: MarginaliaPageQuery = {},
  client: ApiClient = apiClient,
): Promise<Page<MarginaliaBookSummary>> {
  const response = await client.request<ApiPage<BookSummaryResponse>>(
    withQuery("/api/v1/marginalia/books/", pageQuery(query)),
  );
  return toPage(response, mapBookSummary);
}

export async function getMarginaliaBook(
  bookId: string,
  client: ApiClient = apiClient,
): Promise<MarginaliaBookSummary> {
  return mapBookSummary(await client.request<BookSummaryResponse>(bookPath(bookId)));
}

export async function listMarginaliaBookSessions(
  bookId: string,
  query: MarginaliaSessionsQuery = {},
  client: ApiClient = apiClient,
): Promise<MarginaliaBookSessionsPage> {
  const response = await client.request<BookSessionsPageResponse>(
    withQuery(`${bookPath(bookId)}sessions/`, sessionQuery(query)),
  );
  return {
    ...toPage(response, mapSessionSummary),
    book: mapBookSummary(response.context.book),
  };
}

export async function listMarginaliaSessions(
  query: MarginaliaSessionsQuery = {},
  client: ApiClient = apiClient,
): Promise<Page<MarginaliaSessionListItem>> {
  const response = await client.request<ApiPage<GlobalSessionSummaryResponse>>(
    withQuery("/api/v1/marginalia/sessions/", sessionQuery(query)),
  );
  return toPage(response, (item) => ({
    ...mapSessionSummary(item),
    book: mapBookReference(item.book),
  }));
}

export async function listRecentMarginaliaSessions(
  query: RecentMarginaliaSessionsQuery = {},
  client: ApiClient = apiClient,
): Promise<RecentMarginaliaSession[]> {
  const parameters = new URLSearchParams();
  if (query.limit !== undefined) parameters.set("limit", String(query.limit));
  if (query.includeClosed) parameters.set("include_closed", "true");
  const response = await client.request<RecentSessionsResponse>(
    withQuery("/api/v1/marginalia/sessions/recent/", parameters),
  );
  return response.results.map((item) => ({
    id: item.id,
    name: item.name,
    status: item.status,
    lastActivityAt: item.last_activity_at,
    book: mapBookReference(item.book),
    progress: item.progress ? mapProgress(item.progress) : null,
  }));
}

export async function getMarginaliaSession(
  sessionId: string,
  client: ApiClient = apiClient,
): Promise<MarginaliaSessionEnvelope> {
  return mapSessionEnvelope(await client.request<SessionEnvelopeResponse>(sessionPath(sessionId)));
}

export async function updateMarginaliaSession(
  sessionId: string,
  input: MarginaliaSessionMetadataInput,
  client: ApiClient = apiClient,
): Promise<MarginaliaSessionEnvelope> {
  const response = await client.request<SessionEnvelopeResponse>(sessionPath(sessionId), jsonRequest("PATCH", input));
  return mapSessionEnvelope(response);
}

export async function closeMarginaliaSession(
  sessionId: string,
  input: MarginaliaSessionCloseInput = {},
  client: ApiClient = apiClient,
): Promise<MarginaliaSessionEnvelope> {
  const response = await client.request<SessionEnvelopeResponse>(
    `${sessionPath(sessionId)}close/`,
    jsonRequest("POST", input),
  );
  return mapSessionEnvelope(response);
}

export async function listMarginaliaSessionAnnotations(
  sessionId: string,
  client: ApiClient = apiClient,
): Promise<MarginaliaAnnotation[]> {
  const response = await client.request<AnnotationCollectionResponse>(`${sessionPath(sessionId)}annotations/`);
  return response.annotations.map(mapAnnotation);
}

export function downloadCompleteMarginaliaExport(
  input: CompleteMarginaliaExportInput = {},
  client: AttachmentApiClient = apiClient,
): Promise<AttachmentDownload> {
  const parameters = new URLSearchParams();
  if (input.includeEmptySessions) parameters.set("include_empty_sessions", "true");
  return client.requestAttachment(
    withQuery("/api/v1/marginalia/export/", parameters),
    undefined,
    "second-pass-marginalia.json",
    marginaliaExportErrorFromPayload,
  );
}

export function downloadSelectedMarginaliaExport(
  input: SelectedMarginaliaExportInput,
  client: AttachmentApiClient = apiClient,
): Promise<AttachmentDownload> {
  return client.requestAttachment(
    "/api/v1/marginalia/export/",
    jsonRequest("POST", {
      reading_session_ids: input.readingSessionIds,
      include_empty_sessions: input.includeEmptySessions ?? false,
    }),
    "second-pass-marginalia.json",
    marginaliaExportErrorFromPayload,
  );
}

function marginaliaExportErrorFromPayload(status: number, payload: unknown): ApiError {
  const fallback = apiErrorFromPayload(status, payload);
  if (status !== 413 || fallback.code !== "EXPORT_TOO_LARGE" || !isRecord(payload)) {
    return fallback;
  }
  const error = payload.error;
  if (!isRecord(error) || !isRecord(error.limit)) return fallback;
  const guidance = error.hint;
  const exportMode = error.export_mode;
  const limitKind = error.limit.kind;
  const maximum = error.limit.maximum;
  if (
    typeof guidance !== "string"
    || !guidance
    || (exportMode !== "full" && exportMode !== "selected")
    || !isMarginaliaExportLimitKind(limitKind)
    || typeof maximum !== "number"
    || !Number.isSafeInteger(maximum)
    || maximum < 1
  ) return fallback;
  return new MarginaliaExportTooLargeError({
    message: fallback.message,
    guidance,
    exportMode,
    limitKind,
    maximum,
  });
}

function isMarginaliaExportLimitKind(value: unknown): value is MarginaliaExportLimitKind {
  return typeof value === "string" && new Set<MarginaliaExportLimitKind>([
    "selected_sessions",
    "full_sessions",
    "annotations",
    "estimated_archive_bytes",
    "archive_bytes",
  ]).has(value as MarginaliaExportLimitKind);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function mapBookSummary(item: BookSummaryResponse): MarginaliaBookSummary {
  return {
    id: item.id,
    title: item.title,
    authors: item.authors.map((author) => ({ ...author })),
    series: item.series ? {
      id: item.series.id,
      name: item.series.name,
      seriesIndex: item.series.series_index,
    } : null,
    coverUrl: item.cover_url === null ? null : sameOriginUrl(item.cover_url),
    canOpen: item.can_open,
    sessionCount: item.session_count,
    activeSessionCount: item.active_session_count,
    lastActivityAt: item.last_activity_at,
  };
}

function mapBookReference(item: BookReferenceResponse): MarginaliaBookReference {
  return {
    id: item.id,
    title: item.title,
    coverUrl: item.cover_url === null ? null : sameOriginUrl(item.cover_url),
    canOpen: item.can_open,
  };
}

function mapSessionSummary(item: SessionSummaryResponse): MarginaliaSessionSummary {
  return {
    id: item.id,
    name: item.name,
    notes: item.notes,
    status: item.status,
    startedAt: item.started_at,
    closedAt: item.closed_at,
    updatedAt: item.updated_at,
    lastActivityAt: item.last_activity_at,
    annotationCount: item.annotation_count,
  };
}

function mapSessionDetail(item: SessionDetailResponse): MarginaliaSessionDetail {
  return {
    ...mapSessionSummary(item),
    progress: item.progress ? mapProgress(item.progress) : null,
  };
}

function mapSessionEnvelope(item: SessionEnvelopeResponse): MarginaliaSessionEnvelope {
  return {
    book: mapBookSummary(item.context.book),
    session: mapSessionDetail(item.session),
  };
}

function mapProgress(item: ProgressResponse): MarginaliaProgress {
  return {
    cfi: item.cfi,
    locationLabel: item.location_label,
    updatedAt: item.updated_at,
  };
}

function mapAnnotation(item: AnnotationResponse): MarginaliaAnnotation {
  const base = {
    id: item.id,
    clientId: item.client_id,
    location: { cfi: item.location.cfi, locationLabel: item.location.location_label },
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  };
  return item.kind === "bookmark"
    ? { ...base, kind: "bookmark" }
    : { ...base, kind: "highlight", body: { ...item.body } };
}

function pageQuery(query: MarginaliaPageQuery): URLSearchParams {
  const parameters = new URLSearchParams();
  if (query.q !== undefined) parameters.set("q", query.q);
  if (query.page !== undefined) parameters.set("page", String(query.page));
  if (query.pageSize !== undefined) parameters.set("page_size", String(query.pageSize));
  return parameters;
}

function sessionQuery(query: MarginaliaSessionsQuery): URLSearchParams {
  const parameters = pageQuery(query);
  if (query.status !== undefined) parameters.set("status", query.status);
  if (query.hasAnnotations !== undefined) parameters.set("has_annotations", String(query.hasAnnotations));
  return parameters;
}

function withQuery(path: string, parameters: URLSearchParams): string {
  return parameters.size ? `${path}?${parameters.toString()}` : path;
}

function bookPath(bookId: string): string {
  return `/api/v1/marginalia/books/${encodeURIComponent(bookId)}/`;
}

function sessionPath(sessionId: string): string {
  return `/api/v1/marginalia/sessions/${encodeURIComponent(sessionId)}/`;
}

function jsonRequest(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}
