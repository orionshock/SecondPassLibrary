import type { ReactNode } from "react";

import { PageHeader } from "../../components/ui";
import "./ProductPageShellComponent.css";

export interface ProductPageShellComponentProps {
  title?: ReactNode;
  eyebrow?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function ProductPageShellComponent({
  title,
  eyebrow,
  description,
  actions,
  children,
  className = "",
}: ProductPageShellComponentProps) {
  return <div className={`product-page-shell ${className}`.trim()}>
    {title !== undefined ? <PageHeader eyebrow={eyebrow} title={title} description={description} actions={actions} /> : null}
    {children}
  </div>;
}
