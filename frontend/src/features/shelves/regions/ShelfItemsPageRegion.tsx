import type { Page, ShelfItem, ShelfItemOrdering, ShelfScope } from "@second-pass/spl-api";

import { breadcrumbNavigationState } from "../../../app/navigation/breadcrumbs";
import { Button, ErrorPanel } from "../../../components/UiPrimitives";
import { CompactBookRow } from "../../../shared/books/CompactBookRow";
import { OrderMenu, type OrderMenuOption } from "../../../shared/forms/OrderMenu";
import { Pager } from "../../../shared/pagination/Pager";
import { shelfBookBreadcrumbs } from "../shelvesBreadcrumbs";

const shelfItemOrderingOptions: readonly OrderMenuOption<ShelfItemOrdering>[] = [
  { value: "position", label: "Shelf Order", icon: "format_list_numbered" },
  { value: "-position", label: "Reverse Shelf Order", icon: "format_list_numbered_rtl" },
  { value: "title", label: "Title A-Z", icon: "sort_by_alpha" },
  { value: "-title", label: "Title Z-A", icon: "sort_by_alpha" },
  { value: "author", label: "Author A-Z", icon: "person" },
  { value: "-author", label: "Author Z-A", icon: "person" },
];

export function ShelfItemsPageRegion({ shelfId, shelfName, scope, shelfPath, page, pageNumber, pageSize, ordering, loading, error, onOrderingChange, onPageChange, onPageSizeChange, onRetry }: {
  shelfId: string;
  shelfName: string;
  scope: ShelfScope;
  shelfPath: string;
  page?: Page<ShelfItem>;
  pageNumber: number;
  pageSize: number;
  ordering: ShelfItemOrdering;
  loading: boolean;
  error?: Error;
  onOrderingChange: (ordering: ShelfItemOrdering) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
}) {
  return <section className="shelf-items-region" aria-label="Shelf books">
    <div className="shelf-items-controls">
      <OrderMenu label="Order" ariaLabel="Order shelf books" value={ordering} options={shelfItemOrderingOptions} onChange={onOrderingChange} />
    </div>
    <ShelfItemResults shelfId={shelfId} shelfName={shelfName} scope={scope} shelfPath={shelfPath} page={page} pageNumber={pageNumber} pageSize={pageSize} loading={loading} error={error} onPageChange={onPageChange} onPageSizeChange={onPageSizeChange} onRetry={onRetry} />
  </section>;
}

function ShelfItemResults({ shelfId, shelfName, scope, shelfPath, page, pageNumber, pageSize, loading, error, onPageChange, onPageSizeChange, onRetry }: {
  shelfId: string;
  shelfName: string;
  scope: ShelfScope;
  shelfPath: string;
  page?: Page<ShelfItem>;
  pageNumber: number;
  pageSize: number;
  loading: boolean;
  error?: Error;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
}) {
  if (!page && loading) return <div className="shelf-detail-state" aria-live="polite" aria-busy="true">Loading books...</div>;
  if (!page && error) return <div className="shelf-detail-state"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></div>;
  if (!page) return null;

  return <div className={`shelf-items-results${loading ? " shelf-results--loading" : ""}`} aria-busy={loading}>
    {error ? <div className="shelves-inline-error"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></div> : null}
    {page.items.length === 0 ? <p className="shelf-detail-state muted">This shelf has no visible books.</p> : <div className="shelf-book-rows">
      {page.items.map((item) => <CompactBookRow
        key={item.id}
        book={item.book}
        detailPath={`/library/books/${encodeURIComponent(item.book.id)}`}
        navigationState={breadcrumbNavigationState(shelfBookBreadcrumbs(scope, shelfId, shelfName, item.book.title, shelfPath))}
      />)}
    </div>}
    <Pager page={pageNumber} pageSize={pageSize} count={page.count} hasPrevious={Boolean(page.previous)} hasNext={Boolean(page.next)} itemLabel="Books" onPageChange={onPageChange} onPageSizeChange={onPageSizeChange} />
  </div>;
}
