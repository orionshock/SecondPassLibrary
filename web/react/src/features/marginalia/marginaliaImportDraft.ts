import type { ReadingImportApplyInput, ReadingImportPreview } from "@second-pass/spl-api";

export interface MarginaliaImportSessionDraft {
  selected: boolean;
  name: string;
  notes: string;
}

export type MarginaliaImportDraft = Record<string, MarginaliaImportSessionDraft>;
export type MarginaliaImportBookSelectionState = "none" | "some" | "all";

export function createMarginaliaImportDraft(preview: ReadingImportPreview): MarginaliaImportDraft {
  const draft: MarginaliaImportDraft = {};
  preview.books.forEach((book, bookIndex) => book.sessions.forEach((session, sessionIndex) => {
    draft[marginaliaImportSessionKey(bookIndex, sessionIndex)] = {
      selected: session.willImport,
      name: session.name,
      notes: session.notes,
    };
  }));
  return draft;
}

export function marginaliaImportSelectedCount(draft: MarginaliaImportDraft): number {
  return Object.values(draft).filter((session) => session.selected).length;
}

export function marginaliaImportBookSelectionState(preview: ReadingImportPreview, draft: MarginaliaImportDraft, bookIndex: number): MarginaliaImportBookSelectionState {
  const importable = preview.books[bookIndex]?.sessions.flatMap((session, sessionIndex) => (
    session.willImport ? [draft[marginaliaImportSessionKey(bookIndex, sessionIndex)]?.selected === true] : []
  )) ?? [];
  const selected = importable.filter(Boolean).length;
  if (selected === 0) return "none";
  return selected === importable.length ? "all" : "some";
}

export function withMarginaliaImportBookSelection(preview: ReadingImportPreview, draft: MarginaliaImportDraft, bookIndex: number, selected: boolean): MarginaliaImportDraft {
  const next = { ...draft };
  preview.books[bookIndex]?.sessions.forEach((session, sessionIndex) => {
    if (!session.willImport) return;
    const key = marginaliaImportSessionKey(bookIndex, sessionIndex);
    const current = draft[key];
    if (current) next[key] = { ...current, selected };
  });
  return next;
}

export function buildMarginaliaImportApplyInput(preview: ReadingImportPreview, draft: MarginaliaImportDraft): ReadingImportApplyInput {
  return {
    importToken: preview.importToken,
    books: preview.books.flatMap((book, bookIndex) => {
      const sessions = book.sessions.flatMap((session, sessionIndex) => {
        const value = draft[marginaliaImportSessionKey(bookIndex, sessionIndex)];
        return value?.selected ? [{ exportSessionId: session.exportSessionId, name: value.name, notes: value.notes }] : [];
      });
      return sessions.length ? [{ selectionReference: book.selectionReference, sessions }] : [];
    }),
  };
}

export function marginaliaImportSessionKey(bookIndex: number, sessionIndex: number): string {
  return `${bookIndex}:${sessionIndex}`;
}
