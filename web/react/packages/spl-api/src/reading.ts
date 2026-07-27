import { apiClient, type ApiClient } from "./client";
import { sameOriginUrl } from "./urls";

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
