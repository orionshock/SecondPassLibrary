import type { MouseEvent } from "react";

const INTERACTIVE_SELECTOR = "a, button, input, select, textarea, label, [contenteditable='true']";

export function isNestedInteractiveClick(event: MouseEvent<HTMLElement>): boolean {
  return event.target instanceof Element && event.target.closest(INTERACTIVE_SELECTOR) !== null;
}
