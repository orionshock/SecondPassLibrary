import { useId, useState, type CSSProperties } from "react";

import { MaterialIcon } from "./icons/MaterialIcon";

interface HelpPopoverComponentProps {
  ariaLabel: string;
  mouseoverText: string;
  icon?: string;
  label?: string;
  border?: boolean;
  borderColor?: string;
  color?: string;
}

export function HelpPopoverComponent({ ariaLabel, mouseoverText, icon, label, border = false, borderColor, color }: HelpPopoverComponentProps) {
  const descriptionId = useId();
  const [open, setOpen] = useState(false);
  const style: CSSProperties | undefined = borderColor || color ? { borderColor, color } : undefined;

  return <span className="help-popover" data-open={open}>
    <button
      type="button"
      className={`help-popover__button${label ? " help-popover__button--labelled" : ""}${border ? " help-popover__button--bordered" : ""}`}
      style={style}
      aria-label={ariaLabel}
      aria-describedby={descriptionId}
      aria-expanded={open}
      onClick={() => setOpen((value) => !value)}
    >
      {icon ? <MaterialIcon name={icon} size={16} /> : null}
      {label ? <span>{label}</span> : null}
    </button>
    <span id={descriptionId} className="help-popover__content" role="tooltip">{mouseoverText}</span>
  </span>;
}
