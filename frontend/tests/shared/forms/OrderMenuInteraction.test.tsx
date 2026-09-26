/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OrderMenu } from "../../../src/shared/forms/OrderMenu";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
});

describe("OrderMenu keyboard behavior", () => {
  it("opens from the keyboard, moves focus with arrows, and restores the trigger after selection", async () => {
    const container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    const onChange = vi.fn();
    await act(async () => root?.render(<OrderMenu
      label="Order"
      value="title"
      options={[
        { value: "title", label: "Title", icon: "sort" },
        { value: "author", label: "Author", icon: "person" },
      ] as const}
      onChange={onChange}
    />));

    const trigger = container.querySelector<HTMLButtonElement>('[aria-haspopup="menu"]')!;
    await act(async () => trigger.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true })));
    const options = container.querySelectorAll<HTMLButtonElement>('[role="menuitemradio"]');
    expect(options).toHaveLength(2);
    expect(document.activeElement).toBe(options[0]);

    await act(async () => options[0]!.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true })));
    expect(document.activeElement).toBe(options[1]);
    await act(async () => options[1]!.click());

    expect(onChange).toHaveBeenCalledWith("author");
    expect(document.activeElement).toBe(trigger);
    expect(container.querySelector('[role="menu"]')).toBeNull();
  });

  it("maps the descending Author option to the public ordering value", async () => {
    const container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    const onChange = vi.fn();
    await act(async () => root?.render(<OrderMenu
      label="Order"
      value="title"
      options={[
        { value: "title", label: "Title A-Z", icon: "sort" },
        { value: "-title", label: "Title Z-A", icon: "sort" },
        { value: "author", label: "Author A-Z", icon: "person" },
        { value: "-author", label: "Author Z-A", icon: "person" },
      ] as const}
      onChange={onChange}
    />));

    await act(async () => container.querySelector<HTMLButtonElement>(
      '[aria-haspopup="menu"]',
    )!.click());
    const option = [...container.querySelectorAll<HTMLButtonElement>(
      '[role="menuitemradio"]',
    )].find((item) => item.textContent?.includes("Author Z-A"))!;
    await act(async () => option.click());

    expect(onChange).toHaveBeenCalledOnce();
    expect(onChange).toHaveBeenCalledWith("-author");
  });
});
