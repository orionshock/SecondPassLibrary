import type { Page, ShelfOrdering, ShelfScope, ShelfSummary } from "@second-pass/spl-api";
import { Link } from "react-router-dom";

import { breadcrumbNavigationState } from "../../../app/navigation/breadcrumbs";
import { Button, ErrorPanel, PageHeader } from "../../../components/ui";
import type { BookCoverPreviewItem } from "../../../shared/books/BookCoverPreviewStripComponent";
import { PagerComponent } from "../../../shared/pagination/PagerComponent";
import { ShelfSummaryRowComponent } from "../../../shared/shelves/ShelfSummaryRowComponent";
import { shelfBookBreadcrumbs, shelfDetailBreadcrumbFallback } from "../shelvesBreadcrumbs";
import { shelfEditBreadcrumbs, shelfEditPath, shelfNewBreadcrumbs, shelfNewPath } from "../shelfLifecycle";
import { ShelfScopesPageRegion } from "./ShelfScopesPageRegion";

export function ShelvesListPageRegion({ page, pageNumber, pageSize, scope, ordering, loading, error, onScopeChange, onOrderingChange, onPageChange, onPageSizeChange, onRetry }: {
  page?: Page<ShelfSummary>;
  pageNumber: number;
  pageSize: number;
  scope: ShelfScope;
  ordering: ShelfOrdering;
  loading: boolean;
  error?: Error;
  onScopeChange: (scope: ShelfScope) => void;
  onOrderingChange: (ordering: ShelfOrdering) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
}) {
  return <div className="shelves-list-page">
    <PageHeader title="Shelves" actions={<Link className="button-link button--secondary" to={shelfNewPath()} state={breadcrumbNavigationState(shelfNewBreadcrumbs())}>New Shelf</Link>} />
    <div className="shelves-list-toolbar">
      <ShelfScopesPageRegion activeScope={scope} onScopeChange={onScopeChange} />
      <label className="shelves-ordering">Order
        <select value={ordering} onChange={(event) => onOrderingChange(event.target.value as ShelfOrdering)}>
          <option value="name">Name A-Z</option>
          <option value="-item_count">Most Items</option>
        </select>
      </label>
    </div>
    <ShelvesListResults page={page} pageNumber={pageNumber} pageSize={pageSize} scope={scope} loading={loading} error={error} onPageChange={onPageChange} onPageSizeChange={onPageSizeChange} onRetry={onRetry} />
  </div>;
}

function ShelvesListResults({ page, pageNumber, pageSize, scope, loading, error, onPageChange, onPageSizeChange, onRetry }: {
  page?: Page<ShelfSummary>;
  pageNumber: number;
  pageSize: number;
  scope: ShelfScope;
  loading: boolean;
  error?: Error;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
}) {
  if (!page && loading) return <section className="shelves-state" aria-live="polite" aria-busy="true">Loading shelves...</section>;
  if (!page && error) return <section className="shelves-state"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></section>;
  if (!page) return null;

  return <section className={`shelves-results${loading ? " shelves-results--loading" : ""}`} aria-busy={loading}>
    {error ? <div className="shelves-inline-error"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></div> : null}
    {page.items.length === 0 ? <p className="shelves-state muted">{emptyLabel(scope)}</p> : <div className="shelves-list-rows">
      {page.items.map((shelf) => {
        const detailPath = `/shelves/${encodeURIComponent(shelf.id)}`;
        const previewBooks: BookCoverPreviewItem[] = (shelf.previewBooks ?? []).map((book) => ({
          ...book,
          href: `/library/books/${encodeURIComponent(book.id)}`,
          navigationState: breadcrumbNavigationState(shelfBookBreadcrumbs(shelf.id, shelf.name, book.title)),
        }));
        return <ShelfSummaryRowComponent
          key={shelf.id}
          shelf={shelf}
          detailPath={detailPath}
          navigationState={breadcrumbNavigationState(shelfDetailBreadcrumbFallback(shelf.name))}
          previewBooks={previewBooks}
          actions={shelf.canEdit ? <Link
            className="shelf-summary-row-component__edit"
            to={shelfEditPath(shelf.id)}
            state={breadcrumbNavigationState(shelfEditBreadcrumbs(shelf.id, shelf.name))}
          >Edit</Link> : undefined}
        />;
      })}
    </div>}
    <PagerComponent page={pageNumber} pageSize={pageSize} count={page.count} hasPrevious={Boolean(page.previous)} hasNext={Boolean(page.next)} itemLabel="Shelves" onPageChange={onPageChange} onPageSizeChange={onPageSizeChange} />
  </section>;
}

function emptyLabel(scope: ShelfScope): string {
  if (scope === "shared") return "No shelves are shared with you.";
  if (scope === "group") return "No group shelves are visible.";
  return "You do not have any personal shelves.";
}
