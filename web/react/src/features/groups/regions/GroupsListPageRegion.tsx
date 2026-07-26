import type { LibraryGroup, Page } from "@second-pass/spl-api";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";

import { breadcrumbNavigationState } from "../../../app/navigation/breadcrumbs";
import { Button, ErrorPanel, PageHeader } from "../../../components/ui";
import type { BookCoverPreviewItem } from "../../../shared/books/BookCoverPreviewStripComponent";
import { PagerComponent } from "../../../shared/pagination/PagerComponent";
import { groupBookBreadcrumbs, groupDetailBreadcrumbFallback } from "../groupsBreadcrumbs";
import { GroupRowComponent } from "../components/GroupRowComponent";

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
  ordering: "name" | "-name";
  loading: boolean;
  error?: Error;
  curatorGroupIds: ReadonlySet<string>;
  canCreate: boolean;
  newGroupNavigationState?: unknown;
  onSearchChange: (value: string) => void;
  onSearch: () => void;
  onOrderingChange: (ordering: "name" | "-name") => void;
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
      <label className="groups-ordering">Order
        <select value={ordering} onChange={(event) => onOrderingChange(event.target.value as "name" | "-name")}>
          <option value="name">Name A-Z</option>
          <option value="-name">Name Z-A</option>
        </select>
      </label>
    </section>
    <GroupsListResults
      page={page}
      pageNumber={pageNumber}
      pageSize={pageSize}
      loading={loading}
      error={error}
      curatorGroupIds={curatorGroupIds}
      onPageChange={onPageChange}
      onPageSizeChange={onPageSizeChange}
      onRetry={onRetry}
    />
  </div>;
}

function GroupsListResults({ page, pageNumber, pageSize, loading, error, curatorGroupIds, onPageChange, onPageSizeChange, onRetry }: {
  page?: Page<LibraryGroup>;
  pageNumber: number;
  pageSize: number;
  loading: boolean;
  error?: Error;
  curatorGroupIds: ReadonlySet<string>;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
}) {
  if (!page && loading) return <section className="groups-state" aria-live="polite" aria-busy="true">Loading groups...</section>;
  if (!page && error) return <section className="groups-state"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></section>;
  if (!page) return null;

  return <section className={`groups-results${loading ? " groups-results--loading" : ""}`} aria-busy={loading}>
    {error ? <div className="groups-inline-error"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></div> : null}
    {page.items.length === 0 ? <p className="groups-state muted">No groups match this search.</p> : <div className="groups-list-rows">
      {page.items.map((group) => {
        const detailPath = `/groups/${encodeURIComponent(group.id)}`;
        const detailTrail = groupDetailBreadcrumbFallback(group.name);
        const previewBooks: BookCoverPreviewItem[] = (group.previewBooks ?? []).map((book) => ({
          ...book,
          href: `/library/books/${encodeURIComponent(book.id)}`,
          navigationState: breadcrumbNavigationState(groupBookBreadcrumbs(group.id, group.name, book.title)),
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
    <PagerComponent
      page={pageNumber}
      pageSize={pageSize}
      count={page.count}
      hasPrevious={Boolean(page.previous)}
      hasNext={Boolean(page.next)}
      itemLabel="Groups"
      onPageChange={onPageChange}
      onPageSizeChange={onPageSizeChange}
    />
  </section>;
}
