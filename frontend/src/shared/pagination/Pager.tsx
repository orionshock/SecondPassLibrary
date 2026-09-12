import "./Pager.css";

import type { ReactNode } from "react";

import { Button } from "../../components/UiPrimitives";

export type PagerDensity = "compact" | "full";

export interface PagerProps {
  page: number;
  pageSize: number;
  count: number;
  hasPrevious: boolean;
  hasNext: boolean;
  itemLabel: string;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  pageSizes?: readonly number[];
  density?: PagerDensity;
  ariaLabel?: string;
  actionPrefix?: ReactNode;
}

const defaultPageSizes = [20, 30, 40, 50] as const;

export function Pager({ page, pageSize, count, hasPrevious, hasNext, itemLabel, onPageChange, onPageSizeChange, pageSizes = defaultPageSizes, density = "full", ariaLabel, actionPrefix }: PagerProps) {
  const start = count === 0 ? 0 : ((page - 1) * pageSize) + 1;
  const end = Math.min(count, start + pageSize - 1);

  return <nav className={`pager-component pager-component--${density}`} aria-label={ariaLabel ?? `${itemLabel} pagination`}>
    <span className="pager-component__range">Showing {start}{start ? `-${end}` : ""} of {count}</span>
    {density === "full" ? <label className="pager-component__size">Per page
      <select className="form-control form-control--small form-control--select" aria-label={`${itemLabel} per page`} value={pageSize} onChange={(event) => onPageSizeChange(Number(event.target.value))}>
        {pageSizes.map((size) => <option key={size} value={size}>{size}</option>)}
      </select>
    </label> : null}
    <div className="pager-component__actions">
      {actionPrefix}
      <Button type="button" size="small" tone="secondary" disabled={!hasPrevious} onClick={() => onPageChange(Math.max(1, page - 1))}>Previous</Button>
      <Button type="button" size="small" disabled={!hasNext} onClick={() => onPageChange(page + 1)}>Next</Button>
    </div>
  </nav>;
}
