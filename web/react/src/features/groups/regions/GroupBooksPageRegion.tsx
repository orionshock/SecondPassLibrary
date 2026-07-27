import type { CompactBook, Page } from "@second-pass/spl-api";
import type { FormEvent } from "react";

import { breadcrumbNavigationState } from "../../../app/navigation/breadcrumbs";
import { Button, ErrorPanel } from "../../../components/ui";
import { CompactBookRowComponent } from "../../../shared/books/CompactBookRowComponent";
import { OrderMenuComponent, type OrderMenuOption } from "../../../shared/forms/OrderMenuComponent";
import { PagerComponent } from "../../../shared/pagination/PagerComponent";
import { groupBookBreadcrumbs } from "../groupsBreadcrumbs";
import type { GroupBookOrdering } from "../groupsQuery";

const groupBookOrderingOptions: readonly OrderMenuOption<GroupBookOrdering>[] = [
  { value: "title", label: "Title A-Z", icon: "sort_by_alpha" },
  { value: "-title", label: "Title Z-A", icon: "sort_by_alpha" },
  { value: "author", label: "Author A-Z", icon: "person" },
  { value: "-author", label: "Author Z-A", icon: "person" },
  { value: "series", label: "Series A-Z", icon: "auto_stories" },
  { value: "-series", label: "Series Z-A", icon: "auto_stories" },
];

export function GroupBooksPageRegion({
  groupId,
  groupName,
  isPublicGroup,
  groupPath,
  page,
  pageNumber,
  pageSize,
  search,
  ordering,
  loading,
  error,
  onSearchChange,
  onSearch,
  onOrderingChange,
  onPageChange,
  onPageSizeChange,
  onRetry,
}: {
  groupId: string;
  groupName: string;
  isPublicGroup?: boolean;
  groupPath: string;
  page?: Page<CompactBook>;
  pageNumber: number;
  pageSize: number;
  search: string;
  ordering: GroupBookOrdering;
  loading: boolean;
  error?: Error;
  onSearchChange: (value: string) => void;
  onSearch: () => void;
  onOrderingChange: (ordering: GroupBookOrdering) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSearch();
  }

  return <section className="group-books-region" aria-label="Group books">
    <div className="group-books-controls">
      <form role="search" onSubmit={submit}>
        <label htmlFor="group-books-search">Search</label>
        <input id="group-books-search" value={search} placeholder="Book title..." onChange={(event) => onSearchChange(event.target.value)} />
        <Button type="submit">Search</Button>
      </form>
      <OrderMenuComponent label="Order" ariaLabel="Order group books" value={ordering} options={groupBookOrderingOptions} onChange={onOrderingChange} />
    </div>
    <GroupBooksResults
      groupId={groupId}
      groupName={groupName}
      isPublicGroup={isPublicGroup}
      groupPath={groupPath}
      page={page}
      pageNumber={pageNumber}
      pageSize={pageSize}
      loading={loading}
      error={error}
      onPageChange={onPageChange}
      onPageSizeChange={onPageSizeChange}
      onRetry={onRetry}
    />
  </section>;
}

function GroupBooksResults({ groupId, groupName, isPublicGroup, groupPath, page, pageNumber, pageSize, loading, error, onPageChange, onPageSizeChange, onRetry }: {
  groupId: string;
  groupName: string;
  isPublicGroup?: boolean;
  groupPath: string;
  page?: Page<CompactBook>;
  pageNumber: number;
  pageSize: number;
  loading: boolean;
  error?: Error;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
}) {
  if (!page && loading) return <div className="group-detail-state" aria-live="polite" aria-busy="true">Loading books...</div>;
  if (!page && error) return <div className="group-detail-state"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></div>;
  if (!page) return null;

  return <div className={`group-books-results${loading ? " group-results--loading" : ""}`} aria-busy={loading}>
    {error ? <div className="groups-inline-error"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></div> : null}
    {page.items.length === 0 ? <p className="group-detail-state muted">No books match this group view.</p> : <div className="group-book-rows">
      {page.items.map((book) => {
        const detailPath = `/library/books/${encodeURIComponent(book.id)}`;
        return <CompactBookRowComponent
          key={book.id}
          book={book}
          detailPath={detailPath}
          navigationState={breadcrumbNavigationState(groupBookBreadcrumbs(groupId, groupName, book.title, groupPath, isPublicGroup))}
        />;
      })}
    </div>}
    <PagerComponent
      page={pageNumber}
      pageSize={pageSize}
      count={page.count}
      hasPrevious={Boolean(page.previous)}
      hasNext={Boolean(page.next)}
      itemLabel="Books"
      onPageChange={onPageChange}
      onPageSizeChange={onPageSizeChange}
    />
  </div>;
}
