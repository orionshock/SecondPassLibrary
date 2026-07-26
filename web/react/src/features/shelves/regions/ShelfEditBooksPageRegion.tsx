import type { Page, ShelfItem } from "@second-pass/spl-api";

import { breadcrumbNavigationState } from "../../../app/navigation/breadcrumbs";
import { Button, ErrorPanel } from "../../../components/ui";
import { CompactBookRowComponent } from "../../../shared/books/CompactBookRowComponent";
import { PagerComponent } from "../../../shared/pagination/PagerComponent";
import { shelfBookBreadcrumbs } from "../shelvesBreadcrumbs";

export function ShelfEditBooksPageRegion({ shelfId, shelfName, page, pageNumber, pageSize, loading, error, pendingItemId, controlsDisabled, onRemove, onPageChange, onPageSizeChange, onRetry }: {
  shelfId: string;
  shelfName: string;
  page?: Page<ShelfItem>;
  pageNumber: number;
  pageSize: number;
  loading: boolean;
  error?: Error;
  pendingItemId?: string;
  controlsDisabled?: boolean;
  onRemove: (itemId: string) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
}) {
  if (!page && loading) return <section className="shelf-edit-section-state" aria-live="polite" aria-busy="true">Loading books...</section>;
  if (!page && error) return <section className="shelf-edit-section-state"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></section>;
  if (!page) return null;

  return <section className="shelf-edit-books-region" aria-label="Shelf books" aria-busy={loading}>
    {error ? <div className="shelf-edit-inline-error"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></div> : null}
    {page.items.length === 0 ? <p className="muted">This shelf has no visible books.</p> : <div className="shelf-edit-book-rows">
      {page.items.map((item) => <div className="shelf-edit-book-row" key={item.id}>
        <CompactBookRowComponent
          book={item.book}
          detailPath={`/library/books/${encodeURIComponent(item.book.id)}`}
          navigationState={breadcrumbNavigationState(shelfBookBreadcrumbs(shelfId, shelfName, item.book.title))}
        />
        <Button type="button" className="button--danger" disabled={controlsDisabled || Boolean(pendingItemId)} onClick={() => onRemove(item.id)}>
          {pendingItemId === item.id ? "Removing..." : "Remove"}
        </Button>
      </div>)}
    </div>}
    <PagerComponent page={pageNumber} pageSize={pageSize} count={page.count} hasPrevious={Boolean(page.previous)} hasNext={Boolean(page.next)} itemLabel="Books" onPageChange={onPageChange} onPageSizeChange={onPageSizeChange} />
  </section>;
}
