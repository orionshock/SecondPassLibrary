import { apiClient, type ApiClient } from "../client";
import { toPage, type ApiPage, type Page } from "../pagination";
import { mapBookReference, mapBookSummary, mapProgress, mapSessionEnvelope, mapSessionSummary } from "./mappers";
import { jsonRequest, sessionPath, sessionQuery, withQuery } from "./requests";
import type {
  MarginaliaSessionCloseInput,
  MarginaliaExportCandidate,
  MarginaliaSessionEnvelope,
  MarginaliaSessionListItem,
  MarginaliaSessionMetadataInput,
  MarginaliaSessionsQuery,
  RecentMarginaliaSession,
  RecentMarginaliaSessionsQuery,
} from "./types";
import type { BookSummaryResponse, GlobalSessionSummaryResponse, RecentSessionsResponse, SessionEnvelopeResponse } from "./wire";

export async function listMarginaliaSessions(query: MarginaliaSessionsQuery = {}, client: ApiClient = apiClient): Promise<Page<MarginaliaSessionListItem>> {
  const response = await client.request<ApiPage<GlobalSessionSummaryResponse>>(withQuery("/api/v1/marginalia/sessions/", sessionQuery(query)));
  return toPage(response, (item) => ({ ...mapSessionSummary(item), book: mapBookReference(item.book) }));
}

export async function listMarginaliaExportCandidates(
  query: MarginaliaSessionsQuery = {},
  options: { groupByBook?: boolean } = {},
  client: ApiClient = apiClient,
): Promise<Page<MarginaliaExportCandidate>> {
  const parameters = sessionQuery(query);
  parameters.set("include_book_summary", "true");
  if (options.groupByBook) parameters.set("group_by", "book");
  const response = await client.request<ApiPage<GlobalSessionSummaryResponse & { book: BookSummaryResponse }>>(
    withQuery("/api/v1/marginalia/sessions/", parameters),
  );
  return toPage(response, (item) => ({ ...mapSessionSummary(item), book: mapBookSummary(item.book) }));
}

export async function listRecentMarginaliaSessions(query: RecentMarginaliaSessionsQuery = {}, client: ApiClient = apiClient): Promise<RecentMarginaliaSession[]> {
  const parameters = new URLSearchParams();
  if (query.limit !== undefined) parameters.set("limit", String(query.limit));
  if (query.includeClosed) parameters.set("include_closed", "true");
  const response = await client.request<RecentSessionsResponse>(withQuery("/api/v1/marginalia/sessions/recent/", parameters));
  return response.results.map((item) => ({
    id: item.id,
    name: item.name,
    status: item.status,
    lastActivityAt: item.last_activity_at,
    book: mapBookReference(item.book),
    progress: item.progress ? mapProgress(item.progress) : null,
  }));
}

export async function getMarginaliaSession(sessionId: string, client: ApiClient = apiClient): Promise<MarginaliaSessionEnvelope> {
  return mapSessionEnvelope(await client.request<SessionEnvelopeResponse>(sessionPath(sessionId)));
}

export async function updateMarginaliaSession(
  sessionId: string,
  input: MarginaliaSessionMetadataInput,
  client: ApiClient = apiClient,
): Promise<MarginaliaSessionEnvelope> {
  return mapSessionEnvelope(await client.request<SessionEnvelopeResponse>(sessionPath(sessionId), jsonRequest("PATCH", input)));
}

export async function deleteMarginaliaSession(sessionId: string, client: ApiClient = apiClient): Promise<void> {
  await client.request<void>(sessionPath(sessionId), { method: "DELETE" });
}

export async function closeMarginaliaSession(
  sessionId: string,
  input: MarginaliaSessionCloseInput = {},
  client: ApiClient = apiClient,
): Promise<MarginaliaSessionEnvelope> {
  return mapSessionEnvelope(await client.request<SessionEnvelopeResponse>(`${sessionPath(sessionId)}close/`, jsonRequest("POST", input)));
}
