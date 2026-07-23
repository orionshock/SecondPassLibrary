import type { ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import {
  LibrarySortDropdownComponent,
  LibrarySortMenuComponent,
  librarySortMenuReducer,
  librarySortMenuStateForKey,
} from "../features/library/components/LibrarySortDropdownComponent";
import { libraryStateFromSearchParams, withLibraryChange, type LibraryBookUiOrdering } from "../features/library/libraryQuery";

describe("Library sort dropdown", () => {
  it("shows the current sort in a compact labelled Material Symbols button", () => {
    const markup = renderToStaticMarkup(<LibrarySortDropdownComponent ordering="-author" onOrderingChange={vi.fn()} />);
    expect(markup).toContain("Author Z-A");
    expect(markup).toContain('aria-label="Sort books, current: Author Z-A"');
    expect(markup).toContain('aria-haspopup="menu"');
    expect(markup).toContain('aria-expanded="false"');
    expect(markup).toContain(">person</span>");
    expect(markup).not.toContain("<select");
  });

  it("opens through its state transition and renders six keyboard-focusable menu choices", () => {
    expect(librarySortMenuReducer(false, "toggle")).toBe(true);
    const markup = renderToStaticMarkup(<LibrarySortMenuComponent ordering="series" onSelect={vi.fn()} />);
    expect((markup.match(/role="menuitem"/g) ?? [])).toHaveLength(6);
    for (const label of ["Title A-Z", "Title Z-A", "Author A-Z", "Author Z-A", "Series A-Z", "Series Z-A"]) {
      expect(markup).toContain(label);
    }
    expect(markup).toContain('role="menu" aria-label="Sort books"');
    expect(markup).toMatch(/aria-current="true"[^>]*>.*auto_stories.*Series A-Z/s);
  });

  it("selects through the existing ordering handler, which resets the page", () => {
    let state = libraryStateFromSearchParams(new URLSearchParams("ordering=series&page=4&q=test"));
    const onSelect = vi.fn((ordering: LibraryBookUiOrdering) => {
      state = withLibraryChange(state, { ordering });
    });
    const menu = LibrarySortMenuComponent({ ordering: "series", onSelect });
    const options = (menu as ReactElement<{ children: ReactElement<{ onClick: () => void }>[] }>).props.children;
    options[3]!.props.onClick();
    expect(onSelect).toHaveBeenCalledWith("-author");
    expect(state).toMatchObject({ ordering: "-author", page: 1, q: "test" });
  });

  it("closes on Escape without treating other keys as dismissals", () => {
    expect(librarySortMenuStateForKey(true, "Escape")).toBe(false);
    expect(librarySortMenuStateForKey(true, "ArrowDown")).toBe(true);
    expect(librarySortMenuReducer(true, "close")).toBe(false);
  });
});
