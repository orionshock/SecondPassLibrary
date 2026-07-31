import type { MarginaliaSessionListItem } from "@second-pass/spl-api";

export type MarginaliaExportSelectionMap = ReadonlyMap<string, string>;

export function withMarginaliaExportSessionSelection(current: MarginaliaExportSelectionMap, session: MarginaliaSessionListItem, selected: boolean): MarginaliaExportSelectionMap {
  const next = new Map(current);
  if (selected) next.set(session.id, session.book.id);
  else next.delete(session.id);
  return next;
}

export function withMarginaliaExportPageSelection(current: MarginaliaExportSelectionMap, sessions: readonly MarginaliaSessionListItem[], selected: boolean): MarginaliaExportSelectionMap {
  const next = new Map(current);
  for (const session of sessions) {
    if (selected) next.set(session.id, session.book.id);
    else next.delete(session.id);
  }
  return next;
}

export function marginaliaExportSelectedSessionIds(selection: MarginaliaExportSelectionMap): string[] {
  return [...selection.keys()];
}

export function marginaliaExportSelectedBookCount(selection: MarginaliaExportSelectionMap): number {
  return new Set(selection.values()).size;
}
