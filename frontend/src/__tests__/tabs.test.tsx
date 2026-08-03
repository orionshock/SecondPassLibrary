import type { KeyboardEvent, ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { resolveTabQuery, withTabQuery } from "../app/routing/tabQuery";
import { TabListComponent, tabFocusIndexForKey } from "../shared/tabs/TabListComponent";

const tabs = [
  { id: "details", label: "Details" },
  { id: "books", label: "Books" },
  { id: "members", label: "Members" },
] as const;

describe("TabListComponent", () => {
  it("renders controlled tab semantics and stable panel wiring", () => {
    const markup = renderToStaticMarkup(<TabListComponent
      tabs={tabs}
      activeTab="books"
      onChange={vi.fn()}
      ariaLabel="Example sections"
      idPrefix="example"
    />);

    expect(markup).toContain('role="tablist"');
    expect((markup.match(/role="tab"/g) ?? [])).toHaveLength(3);
    expect(markup).toMatch(/id="example-books-tab"[^>]*aria-controls="example-books-panel"[^>]*aria-selected="true"/);
    expect(markup).toMatch(/id="example-details-tab"[^>]*aria-selected="false"[^>]*tabindex="-1"/);
  });

  it("activates through click, Enter, and Space but not while disabled", () => {
    const onChange = vi.fn();
    const tree = TabListComponent({ tabs, activeTab: "details", onChange, ariaLabel: "Sections" }) as ReactElement<{
      children: ReactElement<{ onClick: () => void; onKeyDown: (event: KeyboardEvent<HTMLButtonElement>) => void }>[];
    }>;
    const buttons = tree.props.children;
    buttons[1]!.props.onClick();
    buttons[2]!.props.onKeyDown({ key: "Enter", preventDefault: vi.fn() } as unknown as KeyboardEvent<HTMLButtonElement>);
    buttons[2]!.props.onKeyDown({ key: " ", preventDefault: vi.fn() } as unknown as KeyboardEvent<HTMLButtonElement>);
    expect(onChange.mock.calls).toEqual([["books"], ["members"], ["members"]]);

    const disabledChange = vi.fn();
    const disabled = TabListComponent({ tabs, activeTab: "details", onChange: disabledChange, ariaLabel: "Sections", disabled: true }) as typeof tree;
    disabled.props.children[1]!.props.onClick();
    disabled.props.children[1]!.props.onKeyDown({ key: "Enter", preventDefault: vi.fn() } as unknown as KeyboardEvent<HTMLButtonElement>);
    expect(disabledChange).not.toHaveBeenCalled();
  });

  it("moves focus with arrow, Home, and End keys without activating", () => {
    expect(tabFocusIndexForKey(0, "ArrowRight", 3)).toBe(1);
    expect(tabFocusIndexForKey(0, "ArrowLeft", 3)).toBe(2);
    expect(tabFocusIndexForKey(1, "Home", 3)).toBe(0);
    expect(tabFocusIndexForKey(1, "End", 3)).toBe(2);
    expect(tabFocusIndexForKey(1, "Enter", 3)).toBeUndefined();

    const onChange = vi.fn();
    const tree = TabListComponent({ tabs, activeTab: "details", onChange, ariaLabel: "Sections" }) as ReactElement<{
      children: ReactElement<{ onKeyDown: (event: KeyboardEvent<HTMLButtonElement>) => void }>[];
    }>;
    const focused = vi.fn();
    const currentTarget = { focus: vi.fn(), parentElement: undefined } as unknown as HTMLButtonElement;
    const nextTarget = { focus: focused } as unknown as HTMLButtonElement;
    Object.assign(currentTarget, {
      parentElement: { querySelectorAll: () => [currentTarget, nextTarget] },
    });
    tree.props.children[0]!.props.onKeyDown({
      key: "ArrowRight",
      currentTarget,
      preventDefault: vi.fn(),
    } as unknown as KeyboardEvent<HTMLButtonElement>);
    expect(focused).toHaveBeenCalledOnce();
    expect(onChange).not.toHaveBeenCalled();
  });
});

describe("tab query helpers", () => {
  const knownTabs = ["details", "books", "members"] as const;

  it("resolves missing, valid, explicit-default, and invalid tabs canonically", () => {
    expect(resolveTabQuery(new URLSearchParams(), knownTabs, "details")).toEqual({
      tab: "details", needsCanonicalReplace: false,
    });
    expect(resolveTabQuery(new URLSearchParams("tab=books"), knownTabs, "details")).toEqual({
      tab: "books", needsCanonicalReplace: false,
    });
    expect(resolveTabQuery(new URLSearchParams("tab=details"), knownTabs, "details")).toEqual({
      tab: "details", needsCanonicalReplace: true,
    });
    expect(resolveTabQuery(new URLSearchParams("tab=unknown"), knownTabs, "details")).toEqual({
      tab: "details", needsCanonicalReplace: true,
    });
  });

  it("omits the default and preserves unrelated query parameters", () => {
    expect(withTabQuery(new URLSearchParams("q=storm&page=2&tab=members"), "details", "details").toString()).toBe("q=storm&page=2");
    expect(withTabQuery(new URLSearchParams("q=storm&page=2"), "books", "details").toString()).toBe("q=storm&page=2&tab=books");
  });
});
