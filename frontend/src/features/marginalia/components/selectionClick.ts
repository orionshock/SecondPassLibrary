import type { MouseEvent } from "react";

const INTERACTIVE_SELECTOR = "a, button, input, select, textarea, label, [contenteditable='true']";

export function isNestedInteractiveClick(event: MouseEvent<HTMLElement>): boolean {
  // The checkbox remains the keyboard and semantic control; row clicks only
  // enlarge the pointer target and must ignore nested controls.
  return event.target instanceof Element && event.target.closest(INTERACTIVE_SELECTOR) !== null;
}
