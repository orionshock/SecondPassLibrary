import type { ApiPage } from "../pagination";
import type { MarginaliaHighlightColor, MarginaliaSessionStatus } from "./types";

export interface BookSummaryResponse {
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
export interface BookReferenceResponse { id: string; title: string; cover_url: string | null; can_open: boolean; }
export interface ProgressResponse { cfi: string; location_label: string; updated_at: string; }
export interface SessionSummaryResponse {
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
export interface GlobalSessionSummaryResponse extends SessionSummaryResponse { book: BookReferenceResponse; }
export interface RecentSessionResponse {
  id: string;
  name: string;
  status: MarginaliaSessionStatus;
  last_activity_at: string;
  book: BookReferenceResponse;
  progress: ProgressResponse | null;
}
export interface RecentSessionsResponse { results: RecentSessionResponse[]; }
export interface SessionDetailResponse extends SessionSummaryResponse { progress: ProgressResponse | null; }
export interface SessionEnvelopeResponse { context: { book: BookSummaryResponse }; session: SessionDetailResponse; }
export interface BookSessionsPageResponse extends ApiPage<SessionSummaryResponse> { context: { book: BookSummaryResponse }; }
interface AnnotationLocationResponse { cfi: string; location_label: string; }
interface AnnotationBaseResponse { id: string; client_id: string; location: AnnotationLocationResponse; created_at: string; updated_at: string; }
interface HighlightResponse extends AnnotationBaseResponse {
  kind: "highlight";
  body: { text: string; prefix: string; suffix: string; color: MarginaliaHighlightColor; note: string };
}
interface BookmarkResponse extends AnnotationBaseResponse { kind: "bookmark"; }
export type AnnotationResponse = HighlightResponse | BookmarkResponse;
export interface AnnotationCollectionResponse { annotations: AnnotationResponse[]; }
