import type { Page } from "../pagination";

export type MarginaliaSessionStatus = "active" | "closed";
export type MarginaliaHighlightColor = "yellow" | "green" | "blue" | "pink" | "purple" | "orange";
export interface MarginaliaAuthor { id: string; name: string; }
export interface MarginaliaSeries { id: string; name: string; seriesIndex: string | null; }
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
export interface MarginaliaBookReference { id: string; title: string; coverUrl: string | null; canOpen: boolean; }
export interface MarginaliaProgress { cfi: string; locationLabel: string; updatedAt: string; }
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
export interface MarginaliaSessionListItem extends MarginaliaSessionSummary { book: MarginaliaBookReference; }
export interface MarginaliaExportCandidate extends MarginaliaSessionSummary { book: MarginaliaBookSummary; }
export interface RecentMarginaliaSession {
  id: string;
  name: string;
  status: MarginaliaSessionStatus;
  lastActivityAt: string;
  book: MarginaliaBookReference;
  progress: MarginaliaProgress | null;
}
export interface MarginaliaSessionDetail extends MarginaliaSessionSummary { progress: MarginaliaProgress | null; }
export interface MarginaliaSessionEnvelope { book: MarginaliaBookSummary; session: MarginaliaSessionDetail; }
export interface MarginaliaBookSessionsPage extends Page<MarginaliaSessionSummary> { book: MarginaliaBookSummary; }
export interface MarginaliaLocation { cfi: string; locationLabel: string; }
interface MarginaliaAnnotationBase { id: string; clientId: string; location: MarginaliaLocation; createdAt: string; updatedAt: string; }
export interface MarginaliaHighlight extends MarginaliaAnnotationBase {
  kind: "highlight";
  body: { text: string; prefix: string; suffix: string; color: MarginaliaHighlightColor; note: string };
}
export interface MarginaliaBookmark extends MarginaliaAnnotationBase { kind: "bookmark"; }
export type MarginaliaAnnotation = MarginaliaHighlight | MarginaliaBookmark;
export interface MarginaliaPageQuery { q?: string; page?: number; pageSize?: number; }
export interface MarginaliaSessionsQuery extends MarginaliaPageQuery { status?: MarginaliaSessionStatus; hasAnnotations?: boolean; }
export interface RecentMarginaliaSessionsQuery { limit?: number; includeClosed?: boolean; }
export interface MarginaliaSessionMetadataInput { name?: string; notes?: string; }
export type MarginaliaSessionCloseInput = MarginaliaSessionMetadataInput;
