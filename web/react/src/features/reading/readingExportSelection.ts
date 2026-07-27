import type { ReadingExportSessionSelection, ReadingSessionSummary } from "@second-pass/spl-api";

export type ReadingExportSelectionMap = ReadonlyMap<string, ReadingExportSessionSelection>;

export function withReadingExportSessionSelection(current: ReadingExportSelectionMap, session: ReadingSessionSummary, selected: boolean): ReadingExportSelectionMap {
  const next = new Map(current);
  if (selected) next.set(session.id, { sessionId: session.id, bookId: session.bookId });
  else next.delete(session.id);
  return next;
}

export function withReadingExportPageSelection(current: ReadingExportSelectionMap, sessions: readonly ReadingSessionSummary[], selected: boolean): ReadingExportSelectionMap {
  const next = new Map(current);
  for (const session of sessions) {
    if (selected) next.set(session.id, { sessionId: session.id, bookId: session.bookId });
    else next.delete(session.id);
  }
  return next;
}

export function readingExportSelectedSessions(selection: ReadingExportSelectionMap): ReadingExportSessionSelection[] {
  return [...selection.values()];
}

export function readingExportSelectedBookCount(selection: ReadingExportSelectionMap): number {
  return new Set([...selection.values()].map((item) => item.bookId)).size;
}
