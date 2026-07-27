import type { KeyboardEvent } from "react";

import "./TabListComponent.css";

export interface TabItem<T extends string> {
  id: T;
  label: string;
}

export interface TabListComponentProps<T extends string> {
  tabs: readonly TabItem<T>[];
  activeTab: T;
  onChange: (tab: T) => void;
  ariaLabel: string;
  disabled?: boolean;
  idPrefix?: string;
}

export function tabButtonId(prefix: string, tab: string): string {
  return `${prefix}-${tab}-tab`;
}

export function tabPanelId(prefix: string, tab: string): string {
  return `${prefix}-${tab}-panel`;
}

export function tabFocusIndexForKey(currentIndex: number, key: string, count: number): number | undefined {
  if (count < 1) return undefined;
  if (key === "Home") return 0;
  if (key === "End") return count - 1;
  if (key === "ArrowRight") return (currentIndex + 1) % count;
  if (key === "ArrowLeft") return (currentIndex - 1 + count) % count;
  return undefined;
}

export function TabListComponent<T extends string>({
  tabs,
  activeTab,
  onChange,
  ariaLabel,
  disabled = false,
  idPrefix,
}: TabListComponentProps<T>) {
  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>, tab: T) {
    if (disabled) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onChange(tab);
      return;
    }

    const buttons = Array.from(
      event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="tab"]:not(:disabled)') ?? [],
    );
    const currentIndex = buttons.indexOf(event.currentTarget);
    const nextIndex = tabFocusIndexForKey(currentIndex, event.key, buttons.length);
    if (nextIndex === undefined) return;
    event.preventDefault();
    buttons[nextIndex]?.focus();
  }

  return <div className="tab-list-component" role="tablist" aria-label={ariaLabel} aria-disabled={disabled || undefined}>
    {tabs.map((tab) => <button
      key={tab.id}
      type="button"
      role="tab"
      id={idPrefix ? tabButtonId(idPrefix, tab.id) : undefined}
      aria-controls={idPrefix ? tabPanelId(idPrefix, tab.id) : undefined}
      aria-selected={activeTab === tab.id}
      tabIndex={activeTab === tab.id ? 0 : -1}
      disabled={disabled}
      onClick={() => { if (!disabled) onChange(tab.id); }}
      onKeyDown={(event) => handleKeyDown(event, tab.id)}
    >{tab.label}</button>)}
  </div>;
}
