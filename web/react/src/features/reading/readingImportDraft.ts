import type { ReadingImportApplyInput, ReadingImportPreview } from "@second-pass/spl-api";

export interface ReadingImportSessionDraft {
  selected: boolean;
  name: string;
  notes: string;
}

export type ReadingImportDraft = Record<string, ReadingImportSessionDraft>;
export type ReadingImportBookSelectionState = "none" | "some" | "all";

export function createReadingImportDraft(preview: ReadingImportPreview): ReadingImportDraft {
  const draft: ReadingImportDraft = {};
  preview.books.forEach((book, bookIndex) => book.sessions.forEach((session, sessionIndex) => {
    draft[readingImportSessionKey(bookIndex, sessionIndex)] = {
      selected: session.willImport,
      name: session.name,
      notes: session.notes,
    };
  }));
  return draft;
}

export function readingImportSelectedCount(draft: ReadingImportDraft): number {
  return Object.values(draft).filter((session) => session.selected).length;
}

export function readingImportBookSelectionState(preview: ReadingImportPreview, draft: ReadingImportDraft, bookIndex: number): ReadingImportBookSelectionState {
  const importable = preview.books[bookIndex]?.sessions.flatMap((session, sessionIndex) => (
    session.willImport ? [draft[readingImportSessionKey(bookIndex, sessionIndex)]?.selected === true] : []
  )) ?? [];
  const selected = importable.filter(Boolean).length;
  if (selected === 0) return "none";
  return selected === importable.length ? "all" : "some";
}

export function withReadingImportBookSelection(preview: ReadingImportPreview, draft: ReadingImportDraft, bookIndex: number, selected: boolean): ReadingImportDraft {
  const next = { ...draft };
  preview.books[bookIndex]?.sessions.forEach((session, sessionIndex) => {
    if (!session.willImport) return;
    const key = readingImportSessionKey(bookIndex, sessionIndex);
    const current = draft[key];
    if (current) next[key] = { ...current, selected };
  });
  return next;
}

export function buildReadingImportApplyInput(preview: ReadingImportPreview, draft: ReadingImportDraft): ReadingImportApplyInput {
  return {
    importToken: preview.importToken,
    books: preview.books.flatMap((book, bookIndex) => {
      const sessions = book.sessions.flatMap((session, sessionIndex) => {
        const value = draft[readingImportSessionKey(bookIndex, sessionIndex)];
        return value?.selected ? [{ exportSessionId: session.exportSessionId, name: value.name, notes: value.notes }] : [];
      });
      return sessions.length ? [{ selectionReference: book.selectionReference, sessions }] : [];
    }),
  };
}

export function readingImportSessionKey(bookIndex: number, sessionIndex: number): string {
  return `${bookIndex}:${sessionIndex}`;
}
