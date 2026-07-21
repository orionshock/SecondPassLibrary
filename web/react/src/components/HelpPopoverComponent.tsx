import { useId, useState } from "react";

import { MaterialIcon } from "./icons/MaterialIcon";

export function HelpPopoverComponent({ label, children }: { label: string; children: string }) {
  const descriptionId = useId();
  const [open, setOpen] = useState(false);

  return <span className="help-popover" data-open={open}>
    <button
      type="button"
      className="help-popover__button"
      aria-label={label}
      aria-describedby={descriptionId}
      aria-expanded={open}
      onClick={() => setOpen((value) => !value)}
    >
      <MaterialIcon name="help" size={16} />
    </button>
    <span id={descriptionId} className="help-popover__content" role="tooltip">{children}</span>
  </span>;
}
