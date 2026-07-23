import { useEffect, useId, useReducer, useRef, type KeyboardEvent } from "react";

import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import type { LibraryOrderingOption, LibraryUiOrdering } from "../libraryQuery";

type SortMenuAction = "toggle" | "close";

export function librarySortMenuReducer(open: boolean, action: SortMenuAction): boolean {
  return action === "toggle" ? !open : false;
}

export function librarySortMenuStateForKey(open: boolean, key: string): boolean {
  return key === "Escape" ? false : open;
}

export function LibrarySortDropdownComponent({ ordering, options, itemLabel, onOrderingChange }: {
  ordering: LibraryUiOrdering;
  options: readonly LibraryOrderingOption[];
  itemLabel: string;
  onOrderingChange: (ordering: LibraryUiOrdering) => void;
}) {
  const [open, dispatch] = useReducer(librarySortMenuReducer, false);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuId = useId();
  const activeChoice = options.find(({ value }) => value === ordering) ?? options[0]!;

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
      aria-label={`Sort ${itemLabel}, current: ${activeChoice.label}`}
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
      options={options}
      itemLabel={itemLabel}
      onSelect={(value) => {
        if (value !== ordering) onOrderingChange(value);
        closeAndRestoreFocus();
      }}
    /> : null}
  </div>;
}

export function LibrarySortMenuComponent({ id, ordering, options, itemLabel, onSelect }: {
  id?: string;
  ordering: LibraryUiOrdering;
  options: readonly LibraryOrderingOption[];
  itemLabel: string;
  onSelect: (ordering: LibraryUiOrdering) => void;
}) {
  return <div id={id} className="library-sort-menu" role="menu" aria-label={`Sort ${itemLabel}`}>
    {options.map((choice) => {
      const active = choice.value === ordering;
      return <button
        key={choice.value}
        type="button"
        role="menuitem"
        aria-current={active ? "true" : undefined}
        className={active ? "active" : ""}
        onClick={() => onSelect(choice.value)}
      >
        <MaterialIcon name={choice.icon} />
        <span>{choice.label}</span>
        {active ? <MaterialIcon name="check" className="library-sort-menu__check" /> : null}
      </button>;
    })}
  </div>;
}
