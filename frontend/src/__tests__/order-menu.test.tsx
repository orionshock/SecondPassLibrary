import type { ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import {
  OrderMenuComponent,
  OrderMenuOptionsComponent,
  orderMenuReducer,
  orderMenuStateForKey,
} from "../shared/forms/OrderMenuComponent";
import { libraryAxisOrderingOptions, libraryBookOrderingOptions, libraryStateFromSearchParams, withLibraryChange, type LibraryUiOrdering } from "../features/library/libraryQuery";

describe("OrderMenuComponent", () => {
  it("shows the inline label and selected option icon in an accessible menu button", () => {
    const markup = renderToStaticMarkup(<OrderMenuComponent
      label="Order"
      ariaLabel="Sort books"
      value="-author"
      options={libraryBookOrderingOptions}
      onChange={vi.fn()}
    />);

    expect(markup).toContain(">Order</span>");
    expect(markup).toContain("Author Z-A");
    expect(markup).toContain('aria-label="Sort books, current: Author Z-A"');
    expect(markup).toContain('aria-haspopup="menu"');
    expect(markup).toContain('aria-expanded="false"');
    expect(markup).toContain(">person</span>");
    expect(markup).not.toContain("<select");
  });

  it("renders every option with its icon and marks the selected option", () => {
    const markup = renderToStaticMarkup(<OrderMenuOptionsComponent
      value="series"
      options={libraryBookOrderingOptions}
      ariaLabel="Sort books"
      onSelect={vi.fn()}
    />);

    expect((markup.match(/role="menuitem"/g) ?? [])).toHaveLength(6);
    for (const label of ["Title A-Z", "Title Z-A", "Author A-Z", "Author Z-A", "Series A-Z", "Series Z-A"]) {
      expect(markup).toContain(label);
    }
    expect((markup.match(/>sort_by_alpha<|>person<|>auto_stories</g) ?? [])).toHaveLength(6);
    expect(markup).toContain('role="menu" aria-label="Sort books"');
    expect(markup).toMatch(/aria-current="true"[^>]*>.*auto_stories.*Series A-Z.*check/s);
  });

  it("selects through the consumer handler and uses the close transition", () => {
    let state = libraryStateFromSearchParams(new URLSearchParams("ordering=series&page=4&q=test"));
    const onSelect = vi.fn((ordering: LibraryUiOrdering) => {
      state = withLibraryChange(state, { ordering });
    });
    const menu = OrderMenuOptionsComponent({ value: "series", options: libraryBookOrderingOptions, ariaLabel: "Sort books", onSelect });
    const options = (menu as ReactElement<{ children: ReactElement<{ onClick: () => void }>[] }>).props.children;
    options[3]!.props.onClick();

    expect(onSelect).toHaveBeenCalledWith("-author");
    expect(state).toMatchObject({ ordering: "-author", page: 1, q: "test" });
    expect(orderMenuReducer(true, "close")).toBe(false);
  });

  it("supports Library axis options and Escape dismissal", () => {
    const markup = renderToStaticMarkup(<OrderMenuOptionsComponent
      value="-book_count"
      options={libraryAxisOrderingOptions}
      ariaLabel="Sort authors"
      onSelect={vi.fn()}
    />);

    expect((markup.match(/role="menuitem"/g) ?? [])).toHaveLength(4);
    for (const label of ["Name A-Z", "Name Z-A", "Most Books", "Fewest Books"]) expect(markup).toContain(label);
    expect(markup).toContain(">library_books</span>");
    expect(orderMenuStateForKey(true, "Escape")).toBe(false);
    expect(orderMenuStateForKey(true, "ArrowDown")).toBe(true);
  });

  it("keeps a disabled menu closed", () => {
    const onChange = vi.fn();
    const markup = renderToStaticMarkup(<OrderMenuComponent
      label="Order"
      value="name"
      options={[{ value: "name", label: "Name A-Z", icon: "sort_by_alpha" }] as const}
      onChange={onChange}
      disabled
    />);

    expect(markup).toContain("disabled");
    expect(markup).toContain('aria-expanded="false"');
    expect(markup).not.toContain('role="menu"');
    expect(onChange).not.toHaveBeenCalled();
  });
});
