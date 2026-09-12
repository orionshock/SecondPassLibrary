/** @vitest-environment happy-dom */

import { act, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BookCoverEditor } from "../../../src/features/library/bookEdit/BookCoverEditor";
import { MarginaliaSessionDeleteDialog } from "../../../src/features/marginalia/sessionDetail/MarginaliaSessionDetailPageRegion";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let container: HTMLDivElement | undefined;
let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  container?.remove();
  root = undefined;
  container = undefined;
});

function mount(element: ReactNode) {
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  return act(async () => root?.render(element));
}

describe("modal focus lifecycle", () => {
  it("enters, traps, dismisses, and restores focus for the cover editor", async () => {
    await mount(<BookCoverEditor
      coverUrl={null}
      title="Book"
      inputResetKey={0}
      state={{ pending: false }}
      onFileChange={vi.fn()}
      onReplace={vi.fn()}
      onClear={vi.fn()}
    />);
    const trigger = container!.querySelector<HTMLButtonElement>(".book-cover-editor__trigger")!;
    await act(async () => trigger.click());

    const dialog = container!.querySelector<HTMLElement>('[role="dialog"]')!;
    const buttons = dialog.querySelectorAll<HTMLButtonElement>("button");
    expect(document.activeElement).toBe(buttons[0]);

    buttons[buttons.length - 1]!.focus();
    await act(async () => dialog.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", bubbles: true })));
    expect(document.activeElement).toBe(buttons[0]);

    await act(async () => dialog.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })));
    expect(container!.querySelector('[role="dialog"]')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it("traps forward and reverse focus in the Session delete dialog", async () => {
    const onCancel = vi.fn();
    await mount(<MarginaliaSessionDeleteDialog
      sessionName="Session"
      bookTitle="Book"
      pending={false}
      exportState={{ pending: false }}
      onCancel={onCancel}
      onContinue={vi.fn()}
      onExport={vi.fn()}
    />);

    const dialog = container!.querySelector<HTMLElement>('[role="dialog"]')!;
    const buttons = dialog.querySelectorAll<HTMLButtonElement>("button");
    expect(document.activeElement).toBe(buttons[1]);

    buttons[0]!.focus();
    await act(async () => dialog.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", shiftKey: true, bubbles: true })));
    expect(document.activeElement).toBe(buttons[2]);

    await act(async () => dialog.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })));
    expect(onCancel).toHaveBeenCalledOnce();
  });
});
