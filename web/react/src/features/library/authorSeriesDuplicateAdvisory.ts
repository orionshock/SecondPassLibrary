import type { LibraryAuthor, LibrarySeries } from "@second-pass/spl-api";

import {
  libraryEntityAxisPath,
  libraryEntityBreadcrumbs,
  libraryEntityEditPath,
  libraryEntityNavigationState,
  type LibraryEntityEditMode,
  type LibraryEntityKind,
} from "./authorSeriesLifecycle";

export const duplicateAdvisoryMinimumLength = 2;
export const duplicateAdvisoryResultLimit = 10;
export const duplicateAdvisoryDebounceMs = 250;

export type DuplicateAdvisoryCandidate = Pick<
  LibraryAuthor | LibrarySeries,
  "id" | "name" | "sortName" | "bookCount"
>;

export function duplicateAdvisorySearchTerm(
  value: string,
  mode: LibraryEntityEditMode,
  originalName?: string,
): string | undefined {
  const term = value.trim();
  if (term.length < duplicateAdvisoryMinimumLength) return undefined;
  if (mode === "edit" && originalName !== undefined && value === originalName) return undefined;
  return term;
}

export function scheduleDuplicateAdvisorySearch(
  search: () => void,
  delay = duplicateAdvisoryDebounceMs,
): () => void {
  const timer = setTimeout(search, delay);
  return () => clearTimeout(timer);
}

export class DuplicateAdvisoryRequestGate {
  private generation = 0;

  next(): number {
    this.generation += 1;
    return this.generation;
  }

  invalidate(): void {
    this.generation += 1;
  }

  isCurrent(generation: number): boolean {
    return generation === this.generation;
  }
}

export function duplicateCandidateEditNavigation(
  kind: LibraryEntityKind,
  candidate: DuplicateAdvisoryCandidate,
  returnTo?: string,
) {
  return {
    to: libraryEntityEditPath(kind, candidate.id),
    state: libraryEntityNavigationState({
      breadcrumbs: libraryEntityBreadcrumbs(kind, "edit", candidate.name, candidate.id),
      returnTo: returnTo ?? libraryEntityAxisPath(kind),
    }),
  };
}
