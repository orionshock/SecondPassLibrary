import type { ButtonHTMLAttributes } from "react";

import { IconButton } from "../UiPrimitives";
import { MaterialIcon } from "./MaterialIcon";

export function AddIconButton({
  label,
  title = label,
  ...props
}: Omit<ButtonHTMLAttributes<HTMLButtonElement>, "aria-label" | "children"> & {
  label: string;
}) {
  return <IconButton tone="success" aria-label={label} title={title} {...props}>
    <MaterialIcon name="add" />
  </IconButton>;
}
