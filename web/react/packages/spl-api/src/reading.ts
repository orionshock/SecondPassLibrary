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
