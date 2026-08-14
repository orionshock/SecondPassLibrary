import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";

import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import type { DuplicateAdvisoryCandidate } from "../authorSeriesDuplicateAdvisory";
import { titleKind, type LibraryEntityKind } from "../authorSeriesLifecycle";

export function nextDuplicateAdvisoryOption(
  current: number,
  optionCount: number,
  key: "ArrowDown" | "ArrowUp",
): number {
  if (optionCount < 1) return -1;
  return key === "ArrowDown"
    ? (current + 1 + optionCount) % optionCount
    : (current - 1 + optionCount) % optionCount;
}

export function duplicateAdvisorySelection(
  candidates: readonly DuplicateAdvisoryCandidate[],
  index: number,
): DuplicateAdvisoryCandidate | undefined {
  return candidates[index];
}

export function duplicateAdvisoryDismissesForKey(key: string): boolean {
  return key === "Escape";
}

export function AuthorSeriesNameCombobox({
  kind,
  value,
  enabled,
  candidates,
  pending,
  error,
  onChange,
  onSelectCandidate,
}: {
  kind: LibraryEntityKind;
  value: string;
  enabled: boolean;
  candidates: readonly DuplicateAdvisoryCandidate[];
  pending: boolean;
  error?: Error;
  onChange: (value: string) => void;
  onSelectCandidate: (candidate: DuplicateAdvisoryCandidate) => void;
}) {
  const listboxId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const [focused, setFocused] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const optionCount = candidates.length;
  const expanded = focused && enabled && !dismissed;
  const entity = titleKind(kind);

  useEffect(() => setActiveIndex(-1), [candidates, value]);

  useEffect(() => {
    if (!expanded) return;
    function dismissOutside(event: PointerEvent) {
      if (rootRef.current?.contains(event.target as Node)) return;
      setFocused(false);
      setDismissed(true);
      setActiveIndex(-1);
    }
    document.addEventListener("pointerdown", dismissOutside);
    return () => document.removeEventListener("pointerdown", dismissOutside);
  }, [expanded]);

  function choose(index: number) {
    const selection = duplicateAdvisorySelection(candidates, index);
    setDismissed(true);
    setActiveIndex(-1);
    if (selection) onSelectCandidate(selection);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (duplicateAdvisoryDismissesForKey(event.key) && expanded) {
      event.preventDefault();
      setDismissed(true);
      setActiveIndex(-1);
      return;
    }
    if ((event.key === "ArrowDown" || event.key === "ArrowUp") && enabled) {
      const direction = event.key;
      event.preventDefault();
      setFocused(true);
      setDismissed(false);
      setActiveIndex((current) => nextDuplicateAdvisoryOption(current, optionCount, direction));
      return;
    }
    if (event.key === "Enter" && expanded && activeIndex >= 0) {
      event.preventDefault();
      choose(activeIndex);
    }
  }

  const activeOptionId = activeIndex >= 0 ? `${listboxId}-option-${activeIndex}` : undefined;
  return <div
    className="author-series-name-combobox"
    ref={rootRef}
    onBlur={(event) => {
      if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setFocused(false);
    }}
  >
    <input
      id="library-entity-name"
      role="combobox"
      aria-autocomplete="list"
      aria-expanded={expanded}
      aria-controls={enabled ? listboxId : undefined}
      aria-activedescendant={expanded ? activeOptionId : undefined}
      value={value}
      maxLength={255}
      autoComplete="off"
      onChange={(event) => {
        setDismissed(false);
        onChange(event.target.value);
      }}
      onFocus={() => {
        setFocused(true);
        setDismissed(false);
      }}
      onKeyDown={handleKeyDown}
      autoFocus
    />
    {expanded ? <AuthorSeriesNameSuggestions
      id={listboxId}
      entity={entity}
      candidates={candidates}
      pending={pending}
      error={error}
      activeIndex={activeIndex}
      onChoose={choose}
    /> : null}
  </div>;
}

export function AuthorSeriesNameSuggestions({
  id,
  entity,
  candidates,
  pending,
  error,
  activeIndex,
  onChoose,
}: {
  id: string;
  entity: string;
  candidates: readonly DuplicateAdvisoryCandidate[];
  pending: boolean;
  error?: Error;
  activeIndex: number;
  onChoose: (index: number) => void;
}) {
  return <div id={id} className="author-series-name-combobox__listbox" role="listbox" aria-label={`${entity} name matches`}>
    {pending ? <div className="author-series-name-combobox__status" role="status">Searching...</div> : null}
    {!pending && error ? <div className="author-series-name-combobox__status author-series-name-combobox__status--error" role="status">Search unavailable.</div> : null}
    {!pending && !error && candidates.length === 0 ? <div className="author-series-name-combobox__status" role="status">No existing matches.</div> : null}
    {candidates.map((candidate, index) => <div
        key={candidate.id}
        id={`${id}-option-${index}`}
        className="author-series-name-combobox__option"
        role="option"
        aria-selected={activeIndex === index}
        title={`Jump to ${entity} Edit`}
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => onChoose(index)}
      >
      <MaterialIcon name="arrow_forward" size={16} className="author-series-name-combobox__navigation-icon" />
      <span className="author-series-name-combobox__candidate">
        <span className="author-series-name-combobox__candidate-name">{candidate.name}</span>
        <span className="author-series-name-combobox__candidate-meta">
          {candidate.sortName && candidate.sortName !== candidate.name ? <span>{candidate.sortName}</span> : null}
          <span>{candidate.bookCount} {candidate.bookCount === 1 ? "Book" : "Books"}</span>
        </span>
      </span>
    </div>)}
  </div>;
}
