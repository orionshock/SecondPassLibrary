import type { MarginaliaImportApplyInput, MarginaliaImportPreview } from "@second-pass/spl-api";

export interface MarginaliaImportSessionDraft {
  selected: boolean;
  name: string;
  notes: string;
}

export type MarginaliaImportDraft = Record<string, MarginaliaImportSessionDraft>;
export type MarginaliaImportBookSelectionState = "none" | "some" | "all";

export function createMarginaliaImportDraft(preview: MarginaliaImportPreview): MarginaliaImportDraft {
  const draft: MarginaliaImportDraft = {};
  preview.books.forEach((book) => book.readingSessions.forEach((session) => {
    draft[session.candidateId] = {
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

export function marginaliaImportBookSelectionState(preview: MarginaliaImportPreview, draft: MarginaliaImportDraft, bookCandidateId: string): MarginaliaImportBookSelectionState {
  const importable = preview.books.find((book) => book.candidateId === bookCandidateId)?.readingSessions.flatMap((session) => (
    session.willImport ? [draft[session.candidateId]?.selected === true] : []
  )) ?? [];
  const selected = importable.filter(Boolean).length;
  if (selected === 0) return "none";
  return selected === importable.length ? "all" : "some";
}

export function withMarginaliaImportBookSelection(preview: MarginaliaImportPreview, draft: MarginaliaImportDraft, bookCandidateId: string, selected: boolean): MarginaliaImportDraft {
  const next = { ...draft };
  preview.books.find((book) => book.candidateId === bookCandidateId)?.readingSessions.forEach((session) => {
    if (!session.willImport) return;
    const current = draft[session.candidateId];
    if (current) next[session.candidateId] = { ...current, selected };
  });
  return next;
}

export function buildMarginaliaImportApplyInput(preview: MarginaliaImportPreview, draft: MarginaliaImportDraft): MarginaliaImportApplyInput {
  return {
    importToken: preview.importToken,
    readingSessions: preview.books.flatMap((book) => book.readingSessions.flatMap((session) => {
      const value = draft[session.candidateId];
      if (!session.willImport || !value?.selected) return [];
      return [{
        candidateId: session.candidateId,
        ...(value.name !== session.name ? { name: value.name } : {}),
        ...(value.notes !== session.notes ? { notes: value.notes } : {}),
      }];
    })),
  };
}
