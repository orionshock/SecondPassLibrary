import { useId, useState, type CSSProperties, type KeyboardEvent } from "react";

import { MaterialIcon } from "./icons/MaterialIcon";

interface HelpPopoverProps {
  ariaLabel: string;
  mouseoverText: string;
  icon?: string;
  label?: string;
  border?: boolean;
  borderColor?: string;
  color?: string;
}

export function HelpPopover({ ariaLabel, mouseoverText, icon, label, border = false, borderColor, color }: HelpPopoverProps) {
  const descriptionId = useId();
  const [open, setOpen] = useState(false);
  const style: CSSProperties | undefined = borderColor || color ? { borderColor, color } : undefined;
  const dismiss = (event: KeyboardEvent<HTMLSpanElement>) => {
    if (event.key !== "Escape" || !open) return;
    event.preventDefault();
    setOpen(false);
  };

  return <span className="help-popover" data-open={open} onKeyDown={dismiss}>
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
