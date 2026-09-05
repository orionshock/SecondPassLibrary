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
    expect(container.textContent).toContain(`${initialHtml.length} / 1,000`);

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

  it("uses supported tag controls to edit the raw selection and shared count", async () => {
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);

    function Harness() {
      const [value, setValue] = useState("Alpha beta");
      return <LimitedRichTextEditor
        id="raw-tags"
        value={value}
        maxLength={200}
        onChange={setValue}
      />;
    }

    await act(async () => root?.render(<Harness />));
    expect(container.querySelector('[aria-label="Bold"]')).not.toBeNull();
    expect(container.querySelector('[role="group"][aria-label="Supported HTML tags"]')).toBeNull();
    await act(async () => {
      Array.from(container?.querySelectorAll<HTMLButtonElement>("button") ?? [])
        .find((candidate) => candidate.textContent === "Show raw")
        ?.click();
    });

    const rawToolbar = container.querySelector('[role="group"][aria-label="Supported HTML tags"]');
    const rawButtons = () => Array.from(rawToolbar?.querySelectorAll<HTMLButtonElement>("button") ?? []);
    const button = (label: string) => rawButtons().find((candidate) => candidate.textContent === label);
    expect(rawButtons().map((candidate) => candidate.textContent)).toEqual([
      "<p>", "<br>", "<b>", "<i>", "<ul>", "<ol>", "<li>",
    ]);
    expect(container.querySelector('[aria-label="Bold"]')).toBeNull();

    let raw = container.querySelector<HTMLTextAreaElement>("textarea#raw-tags")!;
    await act(async () => {
      const setValue = Object.getOwnPropertyDescriptor(
        HTMLTextAreaElement.prototype,
        "value",
      )?.set;
      setValue?.call(raw, "Alpha beta");
      raw.dispatchEvent(new Event("input", { bubbles: true }));
    });
    raw = container.querySelector<HTMLTextAreaElement>("textarea#raw-tags")!;
    raw.setSelectionRange(0, 5);
    await act(async () => button("<b>")?.click());
    raw = container.querySelector<HTMLTextAreaElement>("textarea#raw-tags")!;
    expect(raw.value).toBe("<b>Alpha</b> beta");

    const betaStart = raw.value.indexOf("beta");
    raw.setSelectionRange(betaStart, betaStart + 4);
    await act(async () => button("<i>")?.click());
    raw = container.querySelector<HTMLTextAreaElement>("textarea#raw-tags")!;
    raw.setSelectionRange(raw.value.length, raw.value.length);
    await act(async () => button("<br>")?.click());
    raw = container.querySelector<HTMLTextAreaElement>("textarea#raw-tags")!;
    raw.setSelectionRange(0, raw.value.length);
    await act(async () => button("<p>")?.click());
    raw = container.querySelector<HTMLTextAreaElement>("textarea#raw-tags")!;

    expect(raw.value).toBe("<p><b>Alpha</b> <i>beta</i><br></p>");
    expect(container.querySelector(".limited-rich-text-editor__count")?.textContent)
      .toContain(`${raw.value.length} / 200`);

    await act(async () => {
      Array.from(container?.querySelectorAll<HTMLButtonElement>("button") ?? [])
        .find((candidate) => candidate.textContent === "Show rendered")
        ?.click();
    });
    const rendered = container.querySelector<HTMLElement>("#raw-tags")?.innerHTML ?? "";
    expect(rendered).toContain("<strong>Alpha</strong>");
    expect(rendered).toContain("<em>beta</em>");
    expect(rendered).toContain("<br>");
  });

  it("builds a raw list from selected lines", async () => {
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);

    function Harness() {
      const [value, setValue] = useState("One\nTwo");
      return <LimitedRichTextEditor id="raw-list" value={value} onChange={setValue} />;
    }

    await act(async () => root?.render(<Harness />));
    await act(async () => {
      Array.from(container?.querySelectorAll<HTMLButtonElement>("button") ?? [])
        .find((candidate) => candidate.textContent === "Show raw")
        ?.click();
    });
    const rawToolbar = container.querySelector('[role="group"][aria-label="Supported HTML tags"]');
    const findButton = (label: string) => Array.from(
      rawToolbar?.querySelectorAll<HTMLButtonElement>("button") ?? [],
    ).find((candidate) => candidate.textContent === label);
    let raw = container.querySelector<HTMLTextAreaElement>("textarea#raw-list")!;
    await act(async () => {
      const setValue = Object.getOwnPropertyDescriptor(
        HTMLTextAreaElement.prototype,
        "value",
      )?.set;
      setValue?.call(raw, "One\nTwo");
      raw.dispatchEvent(new Event("input", { bubbles: true }));
    });
    raw = container.querySelector<HTMLTextAreaElement>("textarea#raw-list")!;
    raw.setSelectionRange(0, raw.value.length);
    await act(async () => findButton("<ul>")?.click());
    raw = container.querySelector<HTMLTextAreaElement>("textarea#raw-list")!;
    expect(raw.value).toBe("<ul><li>One</li><li>Two</li></ul>");

    await act(async () => {
      Array.from(container?.querySelectorAll<HTMLButtonElement>("button") ?? [])
        .find((candidate) => candidate.textContent === "Show rendered")
        ?.click();
    });
    expect(container.querySelector<HTMLElement>("#raw-list")?.querySelector("ul")).not.toBeNull();
  });

  it("undoes and redoes raw typing and tag edits", async () => {
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);

    function Harness() {
      const [value, setValue] = useState("<p>Start</p>");
      return <LimitedRichTextEditor id="raw-history" value={value} onChange={setValue} />;
    }

    await act(async () => root?.render(<Harness />));
    await act(async () => {
      container?.querySelector<HTMLButtonElement>(".limited-rich-text-editor__mode-control")?.click();
    });

    const historyButton = (label: string) => container
      ?.querySelector<HTMLButtonElement>(`button[aria-label="${label}"]`);
    let raw = container.querySelector<HTMLTextAreaElement>("textarea#raw-history")!;
    expect(historyButton("Undo")?.disabled).toBe(true);
    expect(historyButton("Redo")?.disabled).toBe(true);

    raw.setSelectionRange(3, 8);
    await act(async () => {
      const rawToolbar = container?.querySelector('[role="group"][aria-label="Supported HTML tags"]');
      Array.from(rawToolbar?.querySelectorAll<HTMLButtonElement>("button") ?? [])
        .find((candidate) => candidate.textContent === "<b>")
        ?.click();
    });
    raw = container.querySelector<HTMLTextAreaElement>("textarea#raw-history")!;
    expect(raw.value).toBe("<p><b>Start</b></p>");
    expect(historyButton("Undo")?.disabled).toBe(false);

    await act(async () => historyButton("Undo")?.click());
    expect(container.querySelector<HTMLTextAreaElement>("textarea#raw-history")?.value)
      .toBe("<p>Start</p>");
    expect(historyButton("Redo")?.disabled).toBe(false);

    await act(async () => historyButton("Redo")?.click());
    raw = container.querySelector<HTMLTextAreaElement>("textarea#raw-history")!;
    expect(raw.value).toBe("<p><b>Start</b></p>");

    await act(async () => {
      const setValue = Object.getOwnPropertyDescriptor(
        HTMLTextAreaElement.prototype,
        "value",
      )?.set;
      setValue?.call(raw, "<p>Typed</p>");
      raw.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await act(async () => historyButton("Undo")?.click());
    expect(container.querySelector<HTMLTextAreaElement>("textarea#raw-history")?.value)
      .toBe("<p><b>Start</b></p>");
  });

  it("does not let raw tag controls exceed the shared maximum", async () => {
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);

    function Harness() {
      const [value, setValue] = useState("<p>x</p>");
      return <LimitedRichTextEditor id="raw-limit" value={value} maxLength={12} onChange={setValue} />;
    }

    await act(async () => root?.render(<Harness />));
    await act(async () => {
      Array.from(container?.querySelectorAll<HTMLButtonElement>("button") ?? [])
        .find((candidate) => candidate.textContent === "Show raw")
        ?.click();
    });
    const raw = container.querySelector<HTMLTextAreaElement>("textarea#raw-limit")!;
    raw.setSelectionRange(3, 4);
    const rawToolbar = container.querySelector('[role="group"][aria-label="Supported HTML tags"]');
    await act(async () => {
      Array.from(rawToolbar?.querySelectorAll<HTMLButtonElement>("button") ?? [])
        .find((candidate) => candidate.textContent === "<b>")
        ?.click();
    });

    expect(container.querySelector<HTMLTextAreaElement>("textarea#raw-limit")?.value)
      .toBe("<p>x</p>");
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
    const editorBody = container.querySelector<HTMLElement>(".limited-rich-text-editor__body");
    if (editorBody) editorBody.style.height = "240px";
    await act(async () => {
      container?.querySelector<HTMLButtonElement>(".limited-rich-text-editor__mode-control")?.click();
    });

    const raw = container.querySelector<HTMLTextAreaElement>("textarea#description");
    expect(raw?.value).toBe("<p>About <strong>SPL</strong></p>");
    expect(raw?.maxLength).toBe(1000);
    expect(container.querySelector(".limited-rich-text-editor__body")).toBe(editorBody);
    expect(editorBody?.style.height).toBe("240px");
    expect(container.querySelector(".limited-rich-text-editor__count")?.textContent)
      .toContain(`${raw?.value.length} / 1,000`);

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
    expect(container.querySelector(".limited-rich-text-editor__body")).toBe(editorBody);
    expect(editorBody?.style.height).toBe("240px");
    expect(rendered).toContain("Heading");
    expect(rendered).toContain("Link");
    expect(rendered).not.toMatch(/<(?:h1|a)\b/);
  });
});
