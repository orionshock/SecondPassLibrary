import type { ChangeEvent, SelectHTMLAttributes } from "react";

import { MaterialIcon } from "../../components/icons/MaterialIcon";
import "./OrderSelectComponent.css";

export type OrderSelectIcon =
  | "auto_stories"
  | "format_list_numbered"
  | "format_list_numbered_rtl"
  | "library_books"
  | "person"
  | "sort_by_alpha";

export interface OrderSelectOption<Value extends string> {
  value: Value;
  label: string;
  icon?: OrderSelectIcon;
}

export interface OrderSelectComponentProps<Value extends string> extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "onChange" | "size" | "value"> {
  value: Value;
  options: readonly OrderSelectOption<Value>[];
  onChange: (value: Value) => void;
  label?: string;
  size?: "small" | "medium";
}

export function OrderSelectComponent<Value extends string>({
  value,
  options,
  onChange,
  label = "Order",
  size = "medium",
  className = "",
  ...selectProps
}: OrderSelectComponentProps<Value>) {
  const activeOption = options.find((option) => option.value === value) ?? options[0];

  function change(event: ChangeEvent<HTMLSelectElement>) {
    onChange(event.target.value as Value);
  }

  return <label className="order-select-component">
    <span className="order-select-component__label">{label}</span>
    <span className="order-select-component__control">
      {activeOption?.icon ? <MaterialIcon name={activeOption.icon} /> : null}
      <select
        {...selectProps}
        className={`form-control form-control--${size} form-control--select${activeOption?.icon ? " order-select-component__select--with-icon" : ""} ${className}`.trim()}
        value={value}
        onChange={change}
      >
        {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
    </span>
  </label>;
}
