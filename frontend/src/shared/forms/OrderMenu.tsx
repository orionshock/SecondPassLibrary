import { useEffect, useId, useReducer, useRef, type KeyboardEvent } from "react";

import { MaterialIcon } from "../../components/icons/MaterialIcon";
import "./OrderMenu.css";

type OrderMenuAction = "toggle" | "close";

export interface OrderMenuOption<Value extends string> {
  value: Value;
  label: string;
  icon: string;
}

export interface OrderMenuProps<Value extends string> {
  label: string;
  value: Value;
  options: readonly OrderMenuOption<Value>[];
  onChange: (value: Value) => void;
  ariaLabel?: string;
  size?: "small" | "medium";
  disabled?: boolean;
  className?: string;
}

export function orderMenuReducer(open: boolean, action: OrderMenuAction): boolean {
  return action === "toggle" ? !open : false;
}

export function orderMenuFocusIndexForKey(currentIndex: number, key: string, count: number): number | undefined {
  if (count < 1) return undefined;
  if (key === "Home") return 0;
  if (key === "End") return count - 1;
  if (currentIndex < 0 && key === "ArrowDown") return 0;
  if (currentIndex < 0 && key === "ArrowUp") return count - 1;
  if (key === "ArrowDown") return (currentIndex + 1) % count;
  if (key === "ArrowUp") return (currentIndex - 1 + count) % count;
  return undefined;
}

export function OrderMenu<Value extends string>({
  label,
  value,
  options,
  onChange,
  ariaLabel = label,
  size = "medium",
  disabled = false,
  className = "",
}: OrderMenuProps<Value>) {
  const [open, dispatch] = useReducer(orderMenuReducer, false);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuId = useId();
  const activeOption = options.find((option) => option.value === value) ?? options[0];

  useEffect(() => {
    if (!open) return;
    function dismissOutside(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) dispatch("close");
    }
    document.addEventListener("pointerdown", dismissOutside);
    return () => document.removeEventListener("pointerdown", dismissOutside);
  }, [open]);

  useEffect(() => {
    if (disabled) dispatch("close");
  }, [disabled]);

  useEffect(() => {
    if (!open) return;
    rootRef.current?.querySelector<HTMLButtonElement>('[role="menuitemradio"][aria-checked="true"]')?.focus();
  }, [open]);

  function closeAndRestoreFocus() {
    dispatch("close");
    buttonRef.current?.focus();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape" && open) {
      event.preventDefault();
      event.stopPropagation();
      closeAndRestoreFocus();
      return;
    }
    if (!open) return;
    const items = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="menuitemradio"]'));
    const currentIndex = items.indexOf(document.activeElement as HTMLButtonElement);
    const nextIndex = orderMenuFocusIndexForKey(currentIndex, event.key, items.length);
    if (nextIndex === undefined) return;
    event.preventDefault();
    items[nextIndex]?.focus();
  }

  if (!activeOption) return null;

  return <div className={`order-menu-component ${className}`.trim()}>
    <span className="order-menu-component__label">{label}</span>
    <div
      className="order-menu-component__dropdown"
      ref={rootRef}
      onKeyDown={handleKeyDown}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) dispatch("close");
      }}
    >
      <button
        ref={buttonRef}
        type="button"
        className={`order-menu-component__button order-menu-component__button--${size}`}
        aria-label={`${ariaLabel}, current: ${activeOption.label}`}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        disabled={disabled}
        onClick={() => dispatch("toggle")}
        onKeyDown={(event) => {
          if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
          event.preventDefault();
          dispatch("toggle");
        }}
      >
        <MaterialIcon name={activeOption.icon} />
        <span>{activeOption.label}</span>
        <MaterialIcon name={open ? "expand_less" : "expand_more"} className="order-menu-component__chevron" />
      </button>
      {open ? <OrderMenuOptions
        id={menuId}
        value={value}
        options={options}
        ariaLabel={ariaLabel}
        onSelect={(nextValue) => {
          if (nextValue !== value) onChange(nextValue);
          closeAndRestoreFocus();
        }}
      /> : null}
    </div>
  </div>;
}

export function OrderMenuOptions<Value extends string>({ id, value, options, ariaLabel, onSelect }: {
  id?: string;
  value: Value;
  options: readonly OrderMenuOption<Value>[];
  ariaLabel: string;
  onSelect: (value: Value) => void;
}) {
  return <div id={id} className="order-menu-component__menu" role="menu" aria-label={ariaLabel}>
    {options.map((option) => {
      const active = option.value === value;
      return <button
        key={option.value}
        type="button"
        role="menuitemradio"
        aria-checked={active}
        className={active ? "active" : ""}
        onClick={() => onSelect(option.value)}
      >
        <MaterialIcon name={option.icon} />
        <span>{option.label}</span>
        {active ? <MaterialIcon name="check" className="order-menu-component__check" /> : null}
      </button>;
    })}
  </div>;
}
