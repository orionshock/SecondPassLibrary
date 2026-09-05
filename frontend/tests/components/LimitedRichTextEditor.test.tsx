/** @vitest-environment happy-dom */

import { act } from "react";
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

    await act(async () => root?.render(<LimitedRichTextEditor
      id="description"
      value="<p>About <strong>this server</strong></p><ul><li>Private</li></ul>"
      onChange={onChange}
    />));

    const content = container.querySelector<HTMLElement>("#description");
    expect(content?.innerHTML).toContain("<strong>this server</strong>");
    expect(content?.innerHTML).toContain("<ul><li><p>Private</p></li></ul>");
    expect(onChange).not.toHaveBeenCalled();

    await act(async () => root?.render(<LimitedRichTextEditor
      id="description"
      value="Plain text"
      onChange={onChange}
      disabled
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
      compact
    />));

    const html = container.querySelector<HTMLElement>("#banner")?.innerHTML ?? "";
    expect(html).toContain("Heading");
    expect(html).toContain("Link");
    expect(html).toContain("Quote");
    expect(html).not.toMatch(/<(?:h1|a|blockquote)\b/);
  });
});
