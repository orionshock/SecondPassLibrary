import type {
  AuthorMutationInput,
  LibraryAuthor,
  LibrarySeries,
  SeriesMutationInput,
} from "@second-pass/spl-api";

import { LocalValidationError } from "../../shared/feedback/mutationState";

export interface AuthorSeriesEditDraft {
  name: string;
  sortName: string;
  prose: string;
}

export const emptyAuthorSeriesEditDraft: AuthorSeriesEditDraft = {
  name: "",
  sortName: "",
  prose: "",
};

export function authorEditDraft(author: LibraryAuthor): AuthorSeriesEditDraft {
  return { name: author.name, sortName: author.sortName, prose: author.biography };
}

export function seriesEditDraft(series: LibrarySeries): AuthorSeriesEditDraft {
  return { name: series.name, sortName: series.sortName, prose: series.summary };
}

export function validateAuthorSeriesEditDraft(draft: AuthorSeriesEditDraft): void {
  const fields: Record<string, string[]> = {};
  const name = draft.name.trim();
  if (!name) fields.name = ["Name is required."];
  else if (name.length > 255) fields.name = ["Name must be 255 characters or fewer."];
  if (draft.sortName.trim().length > 255) {
    fields.sortName = ["Sort name must be 255 characters or fewer."];
  }
  if (Object.keys(fields).length) throw new LocalValidationError("Check the highlighted fields.", fields);
}

export function authorMutationInput(draft: AuthorSeriesEditDraft): AuthorMutationInput {
  return { name: draft.name.trim(), sortName: draft.sortName.trim(), biography: draft.prose };
}

export function seriesMutationInput(draft: AuthorSeriesEditDraft): SeriesMutationInput {
  return { name: draft.name.trim(), sortName: draft.sortName.trim(), summary: draft.prose };
}

export function authorSeriesEditDraftsEqual(
  left: AuthorSeriesEditDraft,
  right: AuthorSeriesEditDraft,
): boolean {
  return left.name.trim() === right.name.trim()
    && left.sortName.trim() === right.sortName.trim()
    && left.prose === right.prose;
}
