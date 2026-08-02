import {
  useEffect,
  useId,
  useReducer,
  useRef,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { Link } from "react-router-dom";

import { MaterialIcon } from "../../components/icons/MaterialIcon";

export interface AppMenuItem {
  key: string;
  label: string;
  icon: string;
  active?: boolean;
  to?: string;
  href?: string;
  onSelect?: () => void;
}

export type AppMenuAction = "toggle" | "close" | "open";

export function appMenuReducer(value: boolean, action: AppMenuAction): boolean {
  return action === "toggle" ? !value : action === "open";
}

export function menuTriggerOpensForKey(key: string): boolean {
  return ["ArrowDown", "Enter", " "].includes(key);
}

export function menuIndexForKey(
  currentIndex: number,
  itemCount: number,
  key: string,
): number | null {
  if (itemCount === 0) return null;
  if (key === "Home") return 0;
  if (key === "End") return itemCount - 1;
  if (key === "ArrowDown") return (currentIndex + 1 + itemCount) % itemCount;
  if (key === "ArrowUp") return (currentIndex - 1 + itemCount) % itemCount;
  return null;
}

export function AppMenuComponent({
  className = "",
  trigger,
  triggerLabel,
  triggerTitle,
  menuLabel,
  items,
  active = false,
}: {
  className?: string;
  trigger: ReactNode;
  triggerLabel: string;
  triggerTitle?: string;
  menuLabel: string;
  items: readonly AppMenuItem[];
  active?: boolean;
}) {
  const [open, toggle] = useReducer(appMenuReducer, false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const itemRefs = useRef<Array<HTMLAnchorElement | HTMLButtonElement | null>>([]);
  const menuId = useId();

  useEffect(() => {
    if (!open) return;
    itemRefs.current[0]?.focus();
    function dismissOutside(event: PointerEvent) {
      if (rootRef.current?.contains(event.target as Node)) return;
      toggle("close");
      triggerRef.current?.focus();
    }
    document.addEventListener("pointerdown", dismissOutside);
    return () => document.removeEventListener("pointerdown", dismissOutside);
  }, [open]);

  function closeAndRestoreFocus() {
    toggle("close");
    triggerRef.current?.focus();
  }

  function handleTriggerKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (!menuTriggerOpensForKey(event.key)) return;
    event.preventDefault();
    event.stopPropagation();
    toggle("open");
  }

  function handleMenuKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      closeAndRestoreFocus();
      return;
    }
    const currentIndex = itemRefs.current.findIndex((item) => item === document.activeElement);
    const nextIndex = menuIndexForKey(currentIndex, items.length, event.key);
    if (nextIndex === null) return;
    event.preventDefault();
    itemRefs.current[nextIndex]?.focus();
  }

  return <div
    className={`app-menu-component ${active ? "app-menu-component--active" : ""} ${className}`.trim()}
    ref={rootRef}
    onKeyDown={handleMenuKeyDown}
    onBlur={(event) => {
      if (!event.currentTarget.contains(event.relatedTarget as Node | null)) toggle("close");
    }}
  >
    <button
      ref={triggerRef}
      type="button"
      className="app-menu-component__trigger"
      aria-label={triggerLabel}
      aria-haspopup="menu"
      aria-expanded={open}
      aria-controls={open ? menuId : undefined}
      title={triggerTitle}
      onKeyDown={handleTriggerKeyDown}
      onClick={() => toggle("toggle")}
    >{trigger}</button>
    {open ? <AppMenuItemsComponent
      id={menuId}
      label={menuLabel}
      items={items}
      itemRefs={itemRefs}
      onSelect={() => toggle("close")}
    /> : null}
  </div>;
}

export function AppMenuItemsComponent({
  id,
  label,
  items,
  itemRefs,
  onSelect,
}: {
  id?: string;
  label: string;
  items: readonly AppMenuItem[];
  itemRefs?: { current: Array<HTMLAnchorElement | HTMLButtonElement | null> };
  onSelect: () => void;
}) {
  return <div id={id} className="app-menu-component__menu" role="menu" aria-label={label}>
    {items.map((item, index) => {
      const content = <><MaterialIcon name={item.icon} /><span>{item.label}</span></>;
      const common = {
        role: "menuitem",
        className: item.active ? "active" : "",
        "aria-current": item.active ? "page" as const : undefined,
        onClick: () => {
          onSelect();
          item.onSelect?.();
        },
      };
      if (item.to) return <Link
        key={item.key}
        ref={(element) => { if (itemRefs) itemRefs.current[index] = element; }}
        to={item.to}
        {...common}
      >{content}</Link>;
      if (item.href) return <a
        key={item.key}
        ref={(element) => { if (itemRefs) itemRefs.current[index] = element; }}
        href={item.href}
        {...common}
      >{content}</a>;
      return <button
        key={item.key}
        ref={(element) => { if (itemRefs) itemRefs.current[index] = element; }}
        type="button"
        {...common}
      >{content}</button>;
    })}
  </div>;
}
