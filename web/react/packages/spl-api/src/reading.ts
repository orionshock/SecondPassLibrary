import { apiClient, type ApiClient } from "./client";
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
  hasAnnotations?: boolean;
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
  if (query.hasAnnotations !== undefined) parameters.set("has_annotations", String(query.hasAnnotations));
  const suffix = parameters.size ? `?${parameters.toString()}` : "";
  const response = await client.request<ApiPage<ReadingSessionSummaryResponse>>(
    `/api/v1/reading/sessions/${suffix}`,
  );
  return toPage(response, mapReadingSessionSummary);
}

export async function getReadingSession(sessionId: string, client: ApiClient = apiClient): Promise<ReadingSessionDetail> {
  const item = await client.request<ReadingSessionDetailResponse>(`/api/v1/reading/sessions/${encodeURIComponent(sessionId)}/`);
  return mapReadingSessionDetail(item);
}

export async function updateReadingSession(
  sessionId: string,
  input: { name?: string; notes?: string },
  client: ApiClient = apiClient,
): Promise<ReadingSessionDetail> {
  const item = await client.request<ReadingSessionDetailResponse>(
    `/api/v1/reading/sessions/${encodeURIComponent(sessionId)}/`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    },
  );
  return mapReadingSessionDetail(item);
}

function mapReadingSessionDetail(item: ReadingSessionDetailResponse): ReadingSessionDetail {
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
