import type { ButtonHTMLAttributes } from "react";

import { IconButton } from "../ui";
import { MaterialIcon } from "./MaterialIcon";

export function RemoveIconButton({
  label,
  title = label,
  ...props
}: Omit<ButtonHTMLAttributes<HTMLButtonElement>, "aria-label" | "children"> & {
  label: string;
}) {
  return <IconButton tone="danger" aria-label={label} title={title} {...props}>
    <MaterialIcon name="remove_circle" />
  </IconButton>;
}
