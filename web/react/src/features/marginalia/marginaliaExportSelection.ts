import type { ReadingExportSessionSelection, ReadingSessionSummary } from "@second-pass/spl-api";

export type MarginaliaExportSelectionMap = ReadonlyMap<string, ReadingExportSessionSelection>;

export function withMarginaliaExportSessionSelection(current: MarginaliaExportSelectionMap, session: ReadingSessionSummary, selected: boolean): MarginaliaExportSelectionMap {
  const next = new Map(current);
  if (selected) next.set(session.id, { sessionId: session.id, bookId: session.bookId });
  else next.delete(session.id);
  return next;
}

export function withMarginaliaExportPageSelection(current: MarginaliaExportSelectionMap, sessions: readonly ReadingSessionSummary[], selected: boolean): MarginaliaExportSelectionMap {
  const next = new Map(current);
  for (const session of sessions) {
    if (selected) next.set(session.id, { sessionId: session.id, bookId: session.bookId });
    else next.delete(session.id);
  }
  return next;
}

export function marginaliaExportSelectedSessions(selection: MarginaliaExportSelectionMap): ReadingExportSessionSelection[] {
  return [...selection.values()];
}

export function marginaliaExportSelectedBookCount(selection: MarginaliaExportSelectionMap): number {
  return new Set([...selection.values()].map((item) => item.bookId)).size;
}
