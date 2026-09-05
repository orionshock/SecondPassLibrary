/** @vitest-environment happy-dom */

import { act, useState } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LimitedRichTextEditor } from "../../src/components/LimitedRichTextEditor";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

let container: HTMLDivElement | undefined;
let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  container?.remove();
  root = undefined;
  container = undefined;
});

describe("LimitedRichTextEditor", () => {
  it("loads supported HTML structure and updates when the external value changes", async () => {
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    const onChange = vi.fn();
    const initialHtml = "<p>About <strong>this server</strong></p><ul><li>Private</li></ul>";

    await act(async () => root?.render(<LimitedRichTextEditor
      id="description"
      value={initialHtml}
      onChange={onChange}
      maxLength={1000}
    />));

    const content = container.querySelector<HTMLElement>("#description");
    expect(content?.innerHTML).toContain("<strong>this server</strong>");
    expect(content?.innerHTML).toContain("<ul><li><p>Private</p></li></ul>");
    expect(onChange).not.toHaveBeenCalled();
    expect(container.textContent).toContain(`${initialHtml.length} / 1000`);

    await act(async () => root?.render(<LimitedRichTextEditor
      id="description"
      value="Plain text"
      onChange={onChange}
      disabled
      maxLength={1000}
    />));

    expect(container.querySelector<HTMLElement>("#description")?.textContent).toBe("Plain text");
    expect(container.querySelector<HTMLElement>("#description")?.getAttribute("contenteditable")).toBe("false");
  });

  it("does not retain editor features outside the limited HTML schema", async () => {
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);

    await act(async () => root?.render(<LimitedRichTextEditor
      id="banner"
      value={'<h1>Heading</h1><p><a href="https://example.test">Link</a></p><blockquote>Quote</blockquote>'}
      onChange={vi.fn()}
    />));

    const html = container.querySelector<HTMLElement>("#banner")?.innerHTML ?? "";
    expect(html).toContain("Heading");
    expect(html).toContain("Link");
    expect(html).toContain("Quote");
    expect(html).not.toMatch(/<(?:h1|a|blockquote)\b/);
  });

  it("switches through raw HTML and reapplies the limited editor schema", async () => {
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    const changed = vi.fn();

    function Harness() {
      const [value, setValue] = useState("<p>About <strong>SPL</strong></p>");
      return <LimitedRichTextEditor
        id="description"
        value={value}
        maxLength={1000}
        onChange={(html) => {
          changed(html);
          setValue(html);
        }}
      />;
    }

    await act(async () => root?.render(<Harness />));
    await act(async () => {
      container?.querySelector<HTMLButtonElement>(".limited-rich-text-editor__mode-control")?.click();
    });

    const raw = container.querySelector<HTMLTextAreaElement>("textarea#description");
    expect(raw?.value).toBe("<p>About <strong>SPL</strong></p>");
    expect(raw?.maxLength).toBe(1000);

    await act(async () => {
      if (!raw) return;
      const setValue = Object.getOwnPropertyDescriptor(
        HTMLTextAreaElement.prototype,
        "value",
      )?.set;
      setValue?.call(
        raw,
        '<h1>Heading</h1><p><a href="https://example.test">Link</a></p>',
      );
      raw.dispatchEvent(new Event("input", { bubbles: true }));
    });
    expect(changed).toHaveBeenLastCalledWith(
      '<h1>Heading</h1><p><a href="https://example.test">Link</a></p>',
    );

    await act(async () => {
      container?.querySelector<HTMLButtonElement>(".limited-rich-text-editor__mode-control")?.click();
    });
    const rendered = container.querySelector<HTMLElement>("#description")?.innerHTML ?? "";
    expect(rendered).toContain("Heading");
    expect(rendered).toContain("Link");
    expect(rendered).not.toMatch(/<(?:h1|a)\b/);
  });
});
