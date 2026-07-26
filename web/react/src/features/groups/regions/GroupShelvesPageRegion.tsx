import type { Page, ShelfSummary } from "@second-pass/spl-api";

import { breadcrumbNavigationState } from "../../../app/navigation/breadcrumbs";
import { Button, ErrorPanel } from "../../../components/ui";
import { PagerComponent } from "../../../shared/pagination/PagerComponent";
import { GroupShelfRowComponent } from "../components/GroupShelfRowComponent";
import { groupShelfBreadcrumbs } from "../groupsBreadcrumbs";

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
      {page.items.map((shelf) => <GroupShelfRowComponent
        key={shelf.id}
        shelf={shelf}
        detailPath={`/shelves/${encodeURIComponent(shelf.id)}`}
        navigationState={breadcrumbNavigationState(groupShelfBreadcrumbs(groupId, groupName, shelf.name, groupPath))}
      />)}
    </div>}
    <PagerComponent page={pageNumber} pageSize={pageSize} count={page.count} hasPrevious={Boolean(page.previous)} hasNext={Boolean(page.next)} itemLabel="Shelves" onPageChange={onPageChange} onPageSizeChange={onPageSizeChange} />
  </section>;
}
