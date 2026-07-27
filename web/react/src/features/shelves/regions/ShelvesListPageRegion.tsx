import type { Page, ShelfOrdering, ShelfScope, ShelfSummary } from "@second-pass/spl-api";
import { Link } from "react-router-dom";

import { breadcrumbNavigationState } from "../../../app/navigation/breadcrumbs";
import { Button, ErrorPanel, PageHeader } from "../../../components/ui";
import type { BookCoverPreviewItem } from "../../../shared/books/BookCoverPreviewStripComponent";
import { OrderSelectComponent, type OrderSelectOption } from "../../../shared/forms/OrderSelectComponent";
import { PaginatedListFrameComponent } from "../../../shared/pagination/PaginatedListFrameComponent";
import { ShelfSummaryRowComponent } from "../../../shared/shelves/ShelfSummaryRowComponent";
import { shelfBookBreadcrumbs, shelfDetailBreadcrumbFallback } from "../shelvesBreadcrumbs";
import { shelfNewBreadcrumbs, shelfNewPath } from "../shelfLifecycle";
import { ShelfScopesPageRegion } from "./ShelfScopesPageRegion";

const shelfOrderingOptions: readonly OrderSelectOption<ShelfOrdering>[] = [
  { value: "name", label: "Name A-Z", icon: "sort_by_alpha" },
  { value: "-item_count", label: "Most Items", icon: "library_books" },
];

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
    <PageHeader title="Shelves" actions={<Link className="button-link" to={shelfNewPath()} state={breadcrumbNavigationState(shelfNewBreadcrumbs())}>New Shelf</Link>} />
    <div className="shelves-list-toolbar">
      <ShelfScopesPageRegion activeScope={scope} onScopeChange={onScopeChange} />
    </div>
    <ShelvesListResults page={page} pageNumber={pageNumber} pageSize={pageSize} scope={scope} ordering={ordering} loading={loading} error={error} onOrderingChange={onOrderingChange} onPageChange={onPageChange} onPageSizeChange={onPageSizeChange} onRetry={onRetry} />
  </div>;
}

function ShelvesListResults({ page, pageNumber, pageSize, scope, ordering, loading, error, onOrderingChange, onPageChange, onPageSizeChange, onRetry }: {
  page?: Page<ShelfSummary>;
  pageNumber: number;
  pageSize: number;
  scope: ShelfScope;
  ordering: ShelfOrdering;
  loading: boolean;
  error?: Error;
  onOrderingChange: (ordering: ShelfOrdering) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
}) {
  if (!page && loading) return <section className="shelves-state" aria-live="polite" aria-busy="true">Loading shelves...</section>;
  if (!page && error) return <section className="shelves-state"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></section>;
  if (!page) return null;

  return <section className={`shelves-results${loading ? " shelves-results--loading" : ""}`} aria-busy={loading}>
    {error ? <div className="shelves-inline-error"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></div> : null}
    <PaginatedListFrameComponent page={pageNumber} pageSize={pageSize} count={page.count} hasPrevious={Boolean(page.previous)} hasNext={Boolean(page.next)} itemLabel="Shelves" topControls={<OrderSelectComponent aria-label="Order shelves" size="small" value={ordering} options={shelfOrderingOptions} onChange={onOrderingChange} />} onPageChange={onPageChange} onPageSizeChange={onPageSizeChange}>
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
            name={shelf.name}
            description={shelf.description}
            detailPath={detailPath}
            navigationState={breadcrumbNavigationState(shelfDetailBreadcrumbFallback(shelf.name))}
            previewBooks={previewBooks}
            group={scope === "group" ? shelf.ownerGroup ?? undefined : undefined}
          />;
        })}
      </div>}
    </PaginatedListFrameComponent>
  </section>;
}

function emptyLabel(scope: ShelfScope): string {
  if (scope === "shared") return "No shelves are shared with you.";
  if (scope === "group") return "No group shelves are visible.";
  return "You do not have any personal shelves.";
}
