import { sameOriginUrl } from "../sameOriginUrl";
import type {
  MarginaliaAnnotation,
  MarginaliaBookReference,
  MarginaliaBookSummary,
  MarginaliaProgress,
  MarginaliaSessionDetail,
  MarginaliaSessionEnvelope,
  MarginaliaSessionSummary,
} from "./types";
import type {
  AnnotationResponse,
  BookReferenceResponse,
  BookSummaryResponse,
  ProgressResponse,
  SessionDetailResponse,
  SessionEnvelopeResponse,
  SessionSummaryResponse,
} from "./wire";

export function mapBookSummary(item: BookSummaryResponse): MarginaliaBookSummary {
  return {
    id: item.id,
    title: item.title,
    authors: item.authors.map((author) => ({ ...author })),
    series: item.series ? { id: item.series.id, name: item.series.name, seriesIndex: item.series.series_index } : null,
    coverUrl: item.cover_url === null ? null : sameOriginUrl(item.cover_url),
    canOpen: item.can_open,
    sessionCount: item.session_count,
    activeSessionCount: item.active_session_count,
    lastActivityAt: item.last_activity_at,
  };
}

export function mapBookReference(item: BookReferenceResponse): MarginaliaBookReference {
  return { id: item.id, title: item.title, coverUrl: item.cover_url === null ? null : sameOriginUrl(item.cover_url), canOpen: item.can_open };
}

export function mapSessionSummary(item: SessionSummaryResponse): MarginaliaSessionSummary {
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

export function mapSessionDetail(item: SessionDetailResponse): MarginaliaSessionDetail {
  return { ...mapSessionSummary(item), progress: item.progress ? mapProgress(item.progress) : null };
}

export function mapSessionEnvelope(item: SessionEnvelopeResponse): MarginaliaSessionEnvelope {
  return { book: mapBookSummary(item.context.book), session: mapSessionDetail(item.session) };
}

export function mapProgress(item: ProgressResponse): MarginaliaProgress {
  return { location: item.location, locationLabel: item.location_label, updatedAt: item.updated_at };
}

export function mapAnnotation(item: AnnotationResponse): MarginaliaAnnotation {
  const base = {
    id: item.id,
    clientId: item.client_id,
    location: { location: item.location.location, locationLabel: item.location.location_label },
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  };
  return item.kind === "bookmark" ? { ...base, kind: "bookmark" } : { ...base, kind: "highlight", body: { ...item.body } };
}
