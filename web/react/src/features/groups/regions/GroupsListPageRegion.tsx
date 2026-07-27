import type { LibraryGroup, Page } from "@second-pass/spl-api";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";

import { breadcrumbNavigationState } from "../../../app/navigation/breadcrumbs";
import { Button, ErrorPanel, PageHeader } from "../../../components/ui";
import type { BookCoverPreviewItem } from "../../../shared/books/BookCoverPreviewStripComponent";
import { OrderMenuComponent, type OrderMenuOption } from "../../../shared/forms/OrderMenuComponent";
import { GroupRowComponent } from "../../../shared/groups/GroupRowComponent";
import { PaginatedListFrameComponent } from "../../../shared/pagination/PaginatedListFrameComponent";
import { groupBookBreadcrumbs, groupDetailBreadcrumbFallback } from "../groupsBreadcrumbs";

type GroupsListOrdering = "name" | "-name";

const groupOrderingOptions: readonly OrderMenuOption<GroupsListOrdering>[] = [
  { value: "name", label: "Name A-Z", icon: "sort_by_alpha" },
  { value: "-name", label: "Name Z-A", icon: "sort_by_alpha" },
];

export function GroupsListPageRegion({
  page,
  pageNumber,
  pageSize,
  search,
  ordering,
  loading,
  error,
  curatorGroupIds,
  canCreate,
  newGroupNavigationState,
  onSearchChange,
  onSearch,
  onOrderingChange,
  onPageChange,
  onPageSizeChange,
  onRetry,
}: {
  page?: Page<LibraryGroup>;
  pageNumber: number;
  pageSize: number;
  search: string;
  ordering: GroupsListOrdering;
  loading: boolean;
  error?: Error;
  curatorGroupIds: ReadonlySet<string>;
  canCreate: boolean;
  newGroupNavigationState?: unknown;
  onSearchChange: (value: string) => void;
  onSearch: () => void;
  onOrderingChange: (ordering: GroupsListOrdering) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSearch();
  }

  return <div className="groups-list-page">
    <PageHeader title="Groups" actions={canCreate
      ? <Link className="button" to="/groups/new" state={newGroupNavigationState}>New Group</Link>
      : undefined} />
    <section className="groups-controls" aria-label="Group filters">
      <form role="search" onSubmit={submit}>
        <label htmlFor="groups-search">Search</label>
        <input id="groups-search" value={search} placeholder="Group name or description..." onChange={(event) => onSearchChange(event.target.value)} />
        <Button type="submit">Search</Button>
      </form>
    </section>
    <GroupsListResults
      page={page}
      pageNumber={pageNumber}
      pageSize={pageSize}
      loading={loading}
      error={error}
      ordering={ordering}
      curatorGroupIds={curatorGroupIds}
      onOrderingChange={onOrderingChange}
      onPageChange={onPageChange}
      onPageSizeChange={onPageSizeChange}
      onRetry={onRetry}
    />
  </div>;
}

function GroupsListResults({ page, pageNumber, pageSize, loading, error, ordering, curatorGroupIds, onOrderingChange, onPageChange, onPageSizeChange, onRetry }: {
  page?: Page<LibraryGroup>;
  pageNumber: number;
  pageSize: number;
  loading: boolean;
  error?: Error;
  ordering: GroupsListOrdering;
  curatorGroupIds: ReadonlySet<string>;
  onOrderingChange: (ordering: GroupsListOrdering) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
}) {
  if (!page && loading) return <section className="groups-state" aria-live="polite" aria-busy="true">Loading groups...</section>;
  if (!page && error) return <section className="groups-state"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></section>;
  if (!page) return null;

  return <section className={`groups-results${loading ? " groups-results--loading" : ""}`} aria-busy={loading}>
    {error ? <div className="groups-inline-error"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></div> : null}
    <PaginatedListFrameComponent
      page={pageNumber}
      pageSize={pageSize}
      count={page.count}
      hasPrevious={Boolean(page.previous)}
      hasNext={Boolean(page.next)}
      itemLabel="Groups"
      topControls={<OrderMenuComponent label="Order" ariaLabel="Order groups" size="small" value={ordering} options={groupOrderingOptions} onChange={onOrderingChange} />}
      onPageChange={onPageChange}
      onPageSizeChange={onPageSizeChange}
    >
      {page.items.length === 0 ? <p className="groups-state muted">No groups match this search.</p> : <div className="groups-list-rows">
        {page.items.map((group) => {
          const detailPath = `/groups/${encodeURIComponent(group.id)}`;
          const detailTrail = groupDetailBreadcrumbFallback(group.name, group.isPublicGroup);
          const previewBooks: BookCoverPreviewItem[] = (group.previewBooks ?? []).map((book) => ({
            ...book,
            href: `/library/books/${encodeURIComponent(book.id)}`,
            navigationState: breadcrumbNavigationState(groupBookBreadcrumbs(group.id, group.name, book.title, undefined, group.isPublicGroup)),
          }));
          return <GroupRowComponent
            key={group.id}
            group={group}
            detailPath={detailPath}
            navigationState={breadcrumbNavigationState(detailTrail)}
            isCurator={curatorGroupIds.has(group.id)}
            previewBooks={previewBooks}
          />;
        })}
      </div>}
    </PaginatedListFrameComponent>
  </section>;
}
