import { useEffect, useId, useReducer, useRef, type KeyboardEvent } from "react";

import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import { libraryOrderingOptions, type LibraryBookUiOrdering } from "../libraryQuery";

type SortMenuAction = "toggle" | "close";

export function librarySortMenuReducer(open: boolean, action: SortMenuAction): boolean {
  return action === "toggle" ? !open : false;
}

export function librarySortMenuStateForKey(open: boolean, key: string): boolean {
  return key === "Escape" ? false : open;
}

export function LibrarySortDropdownComponent({ ordering, onOrderingChange }: {
  ordering: LibraryBookUiOrdering;
  onOrderingChange: (ordering: LibraryBookUiOrdering) => void;
}) {
  const [open, dispatch] = useReducer(librarySortMenuReducer, false);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuId = useId();
  const activeChoice = sortChoice(ordering);

  useEffect(() => {
    if (!open) return;
    function dismissOutside(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) dispatch("close");
    }
    document.addEventListener("pointerdown", dismissOutside);
    return () => document.removeEventListener("pointerdown", dismissOutside);
  }, [open]);

  function closeAndRestoreFocus() {
    dispatch("close");
    buttonRef.current?.focus();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (librarySortMenuStateForKey(open, event.key) === open) return;
    event.preventDefault();
    event.stopPropagation();
    closeAndRestoreFocus();
  }

  return <div
    className="library-sort-dropdown"
    ref={rootRef}
    onKeyDown={handleKeyDown}
    onBlur={(event) => {
      if (!event.currentTarget.contains(event.relatedTarget as Node | null)) dispatch("close");
    }}
  >
    <button
      ref={buttonRef}
      type="button"
      className="library-sort-button"
      aria-label={`Sort books, current: ${activeChoice.label}`}
      aria-haspopup="menu"
      aria-expanded={open}
      aria-controls={open ? menuId : undefined}
      onClick={() => dispatch("toggle")}
    >
      <MaterialIcon name={activeChoice.icon} />
      <span>{activeChoice.label}</span>
      <MaterialIcon name={open ? "expand_less" : "expand_more"} className="library-sort-button__chevron" />
    </button>
    {open ? <LibrarySortMenuComponent
      id={menuId}
      ordering={ordering}
      onSelect={(value) => {
        if (value !== ordering) onOrderingChange(value);
        closeAndRestoreFocus();
      }}
    /> : null}
  </div>;
}

export function LibrarySortMenuComponent({ id, ordering, onSelect }: {
  id?: string;
  ordering: LibraryBookUiOrdering;
  onSelect: (ordering: LibraryBookUiOrdering) => void;
}) {
  return <div id={id} className="library-sort-menu" role="menu" aria-label="Sort books">
    {libraryOrderingOptions.map((choice) => {
      const active = choice.value === ordering;
      return <button
        key={choice.value}
        type="button"
        role="menuitem"
        aria-current={active ? "true" : undefined}
        className={active ? "active" : ""}
        onClick={() => onSelect(choice.value)}
      >
        <MaterialIcon name={sortIcon(choice.value)} />
        <span>{choice.label}</span>
        {active ? <MaterialIcon name="check" className="library-sort-menu__check" /> : null}
      </button>;
    })}
  </div>;
}

function sortChoice(ordering: LibraryBookUiOrdering) {
  const choice = libraryOrderingOptions.find(({ value }) => value === ordering)!;
  return { ...choice, icon: sortIcon(ordering) };
}

function sortIcon(ordering: LibraryBookUiOrdering): string {
  if (ordering.includes("author")) return "person";
  if (ordering.includes("series")) return "auto_stories";
  return "sort_by_alpha";
}
