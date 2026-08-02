import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import {
  DuplicateAdvisoryRequestGate,
  duplicateAdvisoryDebounceMs,
  duplicateAdvisoryResultLimit,
  duplicateAdvisorySearchTerm,
  duplicateCandidateEditNavigation,
  scheduleDuplicateAdvisorySearch,
  type DuplicateAdvisoryCandidate,
} from "../features/library/authorSeriesDuplicateAdvisory";
import {
  AuthorSeriesNameComboboxComponent,
  AuthorSeriesNameSuggestionsComponent,
  duplicateAdvisoryDismissesForKey,
  duplicateAdvisorySelection,
  nextDuplicateAdvisoryOption,
} from "../features/library/components/AuthorSeriesNameComboboxComponent";
import { validateAuthorSeriesEditDraft } from "../features/library/authorSeriesEditDraft";

const candidate: DuplicateAdvisoryCandidate = {
  id: "author/id",
  name: "Ada Lovelace",
  sortName: "Lovelace, Ada",
  bookCount: 3,
};

describe("Author and Series duplicate advisory", () => {
  it("starts only for eligible create and changed edit names", () => {
    expect(duplicateAdvisoryResultLimit).toBe(10);
    expect(duplicateAdvisorySearchTerm("A", "new")).toBeUndefined();
    expect(duplicateAdvisorySearchTerm(" Ada ", "new")).toBe("Ada");
    expect(duplicateAdvisorySearchTerm("Ada Lovelace", "edit", "Ada Lovelace")).toBeUndefined();
    expect(duplicateAdvisorySearchTerm(" Ada Lovelace ", "edit", "Ada Lovelace")).toBe("Ada Lovelace");
    expect(duplicateAdvisorySearchTerm("Ada Byron", "edit", "Ada Lovelace")).toBe("Ada Byron");
  });

  it("debounces eligible searches and invalidates stale request generations", () => {
    vi.useFakeTimers();
    const search = vi.fn();
    const cancel = scheduleDuplicateAdvisorySearch(search);
    vi.advanceTimersByTime(duplicateAdvisoryDebounceMs - 1);
    expect(search).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(search).toHaveBeenCalledOnce();
    cancel();
    vi.useRealTimers();

    const gate = new DuplicateAdvisoryRequestGate();
    const stale = gate.next();
    const current = gate.next();
    expect(gate.isCurrent(stale)).toBe(false);
    expect(gate.isCurrent(current)).toBe(true);
    gate.invalidate();
    expect(gate.isCurrent(current)).toBe(false);
  });

  it("renders the combobox contract and bounded candidate metadata without selecting a match", () => {
    const input = renderToStaticMarkup(<AuthorSeriesNameComboboxComponent
      kind="author"
      value="Ada"
      enabled
      candidates={[candidate]}
      pending={false}
      onChange={vi.fn()}
      onSelectCandidate={vi.fn()}
    />);
    expect(input).toContain('role="combobox"');
    expect(input).toContain('aria-expanded="false"');
    expect(input).toContain('autoComplete="off"');
    expect(input).not.toContain('role="listbox"');

    const listbox = renderToStaticMarkup(<AuthorSeriesNameSuggestionsComponent
      id="matches"
      entity="Author"
      candidates={[candidate]}
      pending={false}
      activeIndex={-1}
      onChoose={vi.fn()}
    />);
    expect(listbox).toContain('role="listbox"');
    expect(listbox.match(/role="option"/g)).toHaveLength(1);
    expect(listbox).toContain("Lovelace, Ada");
    expect(listbox).toContain("3 Books");
    expect(listbox).toContain(">arrow_forward</span>");
    expect(listbox).toContain('title="Jump to Author Edit"');
    expect(listbox).toContain('aria-hidden="true"');
    expect(listbox).not.toContain("as a new Author");
    expect(listbox).not.toContain('aria-selected="true"');
  });

  it("maps candidate selection to exact edit routes while duplicate submission remains valid through Save", () => {
    expect(duplicateAdvisorySelection([candidate], 0)).toBe(candidate);
    expect(duplicateAdvisorySelection([candidate], 1)).toBeUndefined();
    expect(duplicateCandidateEditNavigation("author", candidate).to).toBe("/library/authors/author%2Fid/edit");
    expect(duplicateCandidateEditNavigation("series", { ...candidate, id: "series/id" }).to).toBe("/library/series/series%2Fid/edit");
    expect(() => validateAuthorSeriesEditDraft({ name: candidate.name, sortName: "", prose: "" })).not.toThrow();
  });

  it("cycles listbox options predictably and leaves Escape to the combobox dismissal path", () => {
    expect(nextDuplicateAdvisoryOption(-1, 3, "ArrowDown")).toBe(0);
    expect(nextDuplicateAdvisoryOption(2, 3, "ArrowDown")).toBe(0);
    expect(nextDuplicateAdvisoryOption(0, 3, "ArrowUp")).toBe(2);
    expect(nextDuplicateAdvisoryOption(-1, 0, "ArrowDown")).toBe(-1);
    expect(duplicateAdvisoryDismissesForKey("Escape")).toBe(true);
    expect(duplicateAdvisoryDismissesForKey("Enter")).toBe(false);
  });
});
