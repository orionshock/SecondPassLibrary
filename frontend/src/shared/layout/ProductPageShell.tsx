import type { ReactNode } from "react";

import { PageHeader } from "../../components/ui";
import "./ProductPageShell.css";

export interface ProductPageShellProps {
  title?: ReactNode;
  eyebrow?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function ProductPageShell({
  title,
  eyebrow,
  description,
  actions,
  children,
  className = "",
}: ProductPageShellProps) {
  return <div className={`product-page-shell ${className}`.trim()}>
    {title !== undefined ? <PageHeader eyebrow={eyebrow} title={title} description={description} actions={actions} /> : null}
    {children}
  </div>;
}
