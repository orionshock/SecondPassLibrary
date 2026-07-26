import type { Page, ShelfSummary } from "@second-pass/spl-api";

import { breadcrumbNavigationState } from "../../../app/navigation/breadcrumbs";
import { Button, ErrorPanel } from "../../../components/ui";
import type { BookCoverPreviewItem } from "../../../shared/books/BookCoverPreviewStripComponent";
import { PagerComponent } from "../../../shared/pagination/PagerComponent";
import { ShelfSummaryRowComponent } from "../../../shared/shelves/ShelfSummaryRowComponent";
import { groupShelfBookBreadcrumbs, groupShelfBreadcrumbs } from "../groupsBreadcrumbs";

export function GroupShelvesPageRegion({ groupId, groupName, groupPath, page, pageNumber, pageSize, loading, error, onPageChange, onPageSizeChange, onRetry }: {
  groupId: string;
  groupName: string;
  groupPath: string;
  page?: Page<ShelfSummary>;
  pageNumber: number;
  pageSize: number;
  loading: boolean;
  error?: Error;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
}) {
  if (!page && loading) return <section className="group-detail-state" aria-live="polite" aria-busy="true">Loading shelves...</section>;
  if (!page && error) return <section className="group-detail-state"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></section>;
  if (!page) return null;

  return <section className="group-shelves-region" aria-label="Group shelves" aria-busy={loading}>
    {error ? <div className="groups-inline-error"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></div> : null}
    {page.items.length === 0 ? <p className="muted">No shelves yet.</p> : <div className="group-shelf-rows">
      {page.items.map((shelf) => {
        const detailPath = `/shelves/${encodeURIComponent(shelf.id)}`;
        const previewBooks: BookCoverPreviewItem[] = (shelf.previewBooks ?? []).map((book) => ({
          ...book,
          href: `/library/books/${encodeURIComponent(book.id)}`,
          navigationState: breadcrumbNavigationState(groupShelfBookBreadcrumbs(
            groupId, groupName, shelf.id, shelf.name, book.title, groupPath,
          )),
        }));
        return <ShelfSummaryRowComponent
          key={shelf.id}
          name={shelf.name}
          description={shelf.description}
          detailPath={detailPath}
          navigationState={breadcrumbNavigationState(groupShelfBreadcrumbs(groupId, groupName, shelf.name, groupPath))}
          previewBooks={previewBooks}
        />;
      })}
    </div>}
    <PagerComponent page={pageNumber} pageSize={pageSize} count={page.count} hasPrevious={Boolean(page.previous)} hasNext={Boolean(page.next)} itemLabel="Shelves" onPageChange={onPageChange} onPageSizeChange={onPageSizeChange} />
  </section>;
}
