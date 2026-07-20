import { Link } from "react-router-dom";

import type { BreadcrumbItem } from "./breadcrumbs";

export function BreadcrumbsComponent({ items }: { items: readonly BreadcrumbItem[] }) {
  if (items.length === 0) return null;

  return <nav className="app-breadcrumbs" aria-label="Breadcrumb">
    <ol>
      {items.map((item, index) => {
        const current = index === items.length - 1;
        return <li key={`${index}:${item.label}`}>
          {!current && item.to ? <Link to={item.to}>{item.label}</Link> : <span aria-current={current ? "page" : undefined}>{item.label}</span>}
        </li>;
      })}
    </ol>
  </nav>;
}
