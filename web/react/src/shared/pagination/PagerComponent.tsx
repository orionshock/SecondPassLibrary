import "./PagerComponent.css";

export interface PagerComponentProps {
  page: number;
  pageSize: number;
  count: number;
  hasPrevious: boolean;
  hasNext: boolean;
  itemLabel: string;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}

const pageSizes = [20, 50, 100, 200] as const;

export function PagerComponent({ page, pageSize, count, hasPrevious, hasNext, itemLabel, onPageChange, onPageSizeChange }: PagerComponentProps) {
  const start = count === 0 ? 0 : ((page - 1) * pageSize) + 1;
  const end = Math.min(count, start + pageSize - 1);

  return <div className="pager-component" aria-label={`${itemLabel} pagination`}>
    <span className="pager-component__range">Showing {start}{start ? `-${end}` : ""} of {count}</span>
    <label className="pager-component__size">Per page
      <select aria-label={`${itemLabel} per page`} value={pageSize} onChange={(event) => onPageSizeChange(Number(event.target.value))}>
        {pageSizes.map((size) => <option key={size} value={size}>{size}</option>)}
      </select>
    </label>
    <div className="pager-component__actions">
      <button type="button" className="button--secondary" disabled={!hasPrevious} onClick={() => onPageChange(Math.max(1, page - 1))}>Previous</button>
      <button type="button" disabled={!hasNext} onClick={() => onPageChange(page + 1)}>Next</button>
    </div>
  </div>;
}
