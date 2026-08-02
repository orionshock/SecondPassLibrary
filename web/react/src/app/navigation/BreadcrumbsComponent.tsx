import { Link } from "react-router";

import { MaterialIcon } from "../../components/icons/MaterialIcon";
import { breadcrumbIconSymbols, breadcrumbLinkState, type BreadcrumbItem } from "./breadcrumbs";

export function BreadcrumbsComponent({ items }: { items: readonly BreadcrumbItem[] }) {
  if (items.length === 0) return null;

  return <nav className="app-breadcrumbs" aria-label="Breadcrumb">
    <ol>
      {items.map((item, index) => {
        const current = index === items.length - 1;
        const content = <>{item.icon ? <MaterialIcon name={breadcrumbIconSymbols[item.icon]} size={14} /> : null}<span>{item.label}</span></>;
        return <li key={`${index}:${item.label}`}>
          {!current && item.to ? <Link to={item.to} state={breadcrumbLinkState(items, index)}>{content}</Link> : <span aria-current={current ? "page" : undefined}>{content}</span>}
        </li>;
      })}
    </ol>
  </nav>;
}
