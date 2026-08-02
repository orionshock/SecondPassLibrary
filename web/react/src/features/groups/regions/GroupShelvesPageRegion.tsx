import type { Page, ShelfSummary } from "@second-pass/spl-api";
import { Link } from "react-router";

import { breadcrumbNavigationState } from "../../../app/navigation/breadcrumbs";
import { Button, ErrorPanel } from "../../../components/ui";
import type { BookCoverPreviewItem } from "../../../shared/books/BookCoverPreviewStripComponent";
import { PagerComponent } from "../../../shared/pagination/PagerComponent";
import { shelfEditPath } from "../../../shared/shelves/shelfNavigation";
import { ShelfSummaryRowComponent } from "../../../shared/shelves/ShelfSummaryRowComponent";
import { groupShelfBookBreadcrumbs, groupShelfBreadcrumbs, groupShelfEditBreadcrumbs } from "../groupsBreadcrumbs";

export function GroupShelvesPageRegion({ groupId, groupName, isPublicGroup, groupPath, createPath, createNavigationState, page, pageNumber, pageSize, loading, error, onPageChange, onPageSizeChange, onRetry }: {
  groupId: string;
  groupName: string;
  isPublicGroup?: boolean;
  groupPath: string;
  createPath?: string;
  createNavigationState?: unknown;
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
    {createPath ? <div className="group-shelves-region__actions">
      <Link className="button button--small button--secondary" to={createPath} state={createNavigationState}>Create Shelf</Link>
    </div> : null}
    {error ? <div className="groups-inline-error"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></div> : null}
    {page.items.length === 0 ? <p className="muted">No shelves yet.</p> : <div className="group-shelf-rows">
      {page.items.map((shelf) => {
        const detailPath = `/shelves/${encodeURIComponent(shelf.id)}`;
        const previewBooks: BookCoverPreviewItem[] = (shelf.previewBooks ?? []).map((book) => ({
          ...book,
          href: `/library/books/${encodeURIComponent(book.id)}`,
          navigationState: breadcrumbNavigationState(groupShelfBookBreadcrumbs(
            groupId, groupName, shelf.id, shelf.name, book.title, groupPath, isPublicGroup,
          )),
        }));
        const detailNavigationState = breadcrumbNavigationState(groupShelfBreadcrumbs(
          groupId, groupName, shelf.name, groupPath, isPublicGroup,
        ));
        return <ShelfSummaryRowComponent
          key={shelf.id}
          name={shelf.name}
          description={shelf.description}
          itemCount={shelf.itemCount}
          detailPath={detailPath}
          navigationState={detailNavigationState}
          previewBooks={previewBooks}
          actions={shelf.canEdit ? <Link
            className="button button--small button--secondary"
            to={shelfEditPath(shelf.id)}
            state={breadcrumbNavigationState(groupShelfEditBreadcrumbs(
              groupId, groupName, shelf.id, shelf.name, groupPath, isPublicGroup,
            ))}
          >Edit</Link> : undefined}
        />;
      })}
    </div>}
    <PagerComponent page={pageNumber} pageSize={pageSize} count={page.count} hasPrevious={Boolean(page.previous)} hasNext={Boolean(page.next)} itemLabel="Shelves" onPageChange={onPageChange} onPageSizeChange={onPageSizeChange} />
  </section>;
}
