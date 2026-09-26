/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resolveTabQuery, withTabQuery } from "../../../src/app/routing/tabQuery";
import { TabList } from "../../../src/shared/tabs/TabList";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
});

const tabs = [
  { id: "details", label: "Details" },
  { id: "books", label: "Books" },
  { id: "members", label: "Members" },
] as const;

describe("TabList", () => {
  it("renders controlled tab semantics and stable panel wiring", () => {
    const markup = renderToStaticMarkup(<TabList
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

  it("activates through mounted click, Enter, and Space but not while disabled", async () => {
    const container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    const onChange = vi.fn();
    await act(async () => root?.render(<TabList
      tabs={tabs}
      activeTab="details"
      onChange={onChange}
      ariaLabel="Sections"
    />));
    const buttons = container.querySelectorAll<HTMLButtonElement>('[role="tab"]');
    await act(async () => buttons[1]!.click());
    await act(async () => buttons[2]!.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true })));
    await act(async () => buttons[2]!.dispatchEvent(new KeyboardEvent("keydown", { key: " ", bubbles: true })));
    expect(onChange.mock.calls).toEqual([["books"], ["members"], ["members"]]);

    const disabledChange = vi.fn();
    await act(async () => root?.render(<TabList
      tabs={tabs}
      activeTab="details"
      onChange={disabledChange}
      ariaLabel="Sections"
      disabled
    />));
    const disabled = container.querySelectorAll<HTMLButtonElement>('[role="tab"]');
    await act(async () => disabled[1]!.click());
    await act(async () => disabled[1]!.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true })));
    expect(disabledChange).not.toHaveBeenCalled();
  });

  it("moves real focus with arrow, Home, and End keys without activating", async () => {
    const container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    const onChange = vi.fn();
    await act(async () => root?.render(<TabList
      tabs={tabs}
      activeTab="details"
      onChange={onChange}
      ariaLabel="Sections"
    />));
    const buttons = container.querySelectorAll<HTMLButtonElement>('[role="tab"]');
    buttons[0]!.focus();
    for (const [key, expected] of [
      ["ArrowRight", buttons[1]],
      ["End", buttons[2]],
      ["Home", buttons[0]],
      ["ArrowLeft", buttons[2]],
    ] as const) {
      await act(async () => (document.activeElement as HTMLButtonElement).dispatchEvent(
        new KeyboardEvent("keydown", { key, bubbles: true }),
      ));
      expect(document.activeElement).toBe(expected);
    }
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

