import type { ManagedUser, Page, UserOrdering } from "@second-pass/spl-api";

import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import { Button, ErrorPanel } from "../../../components/UiPrimitives";
import { PaginatedListFrame } from "../../../shared/pagination/PaginatedListFrame";
import { UserRow } from "./UserRow";
import { nextUserOrdering } from "./usersListQuery";

export function UsersListPageRegion({ page, pageNumber, pageSize, ordering, advancedGroupsEnabled, loading, error, onOrderingChange, onPageChange, onPageSizeChange, onRetry }: {
  page?: Page<ManagedUser>;
  pageNumber: number;
  pageSize: number;
  ordering: UserOrdering;
  advancedGroupsEnabled: boolean;
  loading: boolean;
  error?: Error;
  onOrderingChange: (ordering: UserOrdering) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
}) {
  if (!page && loading) return <div className="users-results-state" aria-live="polite" aria-busy="true">Loading users...</div>;
  if (!page && error) return <div className="users-results-state"><ErrorPanel>{error.message}</ErrorPanel><div className="users-results-actions"><Button type="button" onClick={onRetry}>Retry</Button></div></div>;
  if (!page) return null;

  return <section className={`users-results${loading ? " users-results--loading" : ""}`} aria-busy={loading}>
    {error ? <div className="users-inline-error"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></div> : null}
    <PaginatedListFrame
      page={pageNumber}
      pageSize={pageSize}
      count={page.count}
      hasPrevious={Boolean(page.previous)}
      hasNext={Boolean(page.next)}
      itemLabel="Users"
      pageSizes={[20, 50, 100, 200]}
      onPageChange={onPageChange}
      onPageSizeChange={onPageSizeChange}
    >
      {page.items.length === 0 ? <p className="users-empty muted">No users match these filters.</p> : <div className="users-table-wrap"><table className="users-table">
        <thead><tr>
          <th><div className="users-heading-group"><SortableControl label="Name" sortKey="name" ordering={ordering} onOrderingChange={onOrderingChange} /><SortableControl label="Username" sortKey="username" ordering={ordering} onOrderingChange={onOrderingChange} /><span>Email</span></div></th>
          <th><div className="users-heading-group"><SortableControl label="Role" sortKey="role" ordering={ordering} onOrderingChange={onOrderingChange} /><SortableControl label="Status" sortKey="is_active" ordering={ordering} onOrderingChange={onOrderingChange} /></div></th>
          <th>Last login</th>
          {advancedGroupsEnabled ? <th>Groups / Curates</th> : null}
          <th className="users-actions-heading">Actions</th>
        </tr></thead>
        <tbody>{page.items.map((user) => <UserRow key={user.id} user={user} showGroups={advancedGroupsEnabled} />)}</tbody>
      </table></div>}
    </PaginatedListFrame>
  </section>;
}

function SortableControl({ label, sortKey, ordering, onOrderingChange }: {
  label: string;
  sortKey: "username" | "name" | "role" | "is_active";
  ordering: UserOrdering;
  onOrderingChange: (ordering: UserOrdering) => void;
}) {
  const active = ordering.replace(/^-/, "") === sortKey;
  const descending = active && ordering.startsWith("-");
  return <button className="users-sort" type="button" aria-label={`Sort by ${label}${active ? `, currently ${descending ? "descending" : "ascending"}` : ""}`} onClick={() => onOrderingChange(nextUserOrdering(ordering, sortKey))}>
    {label}<MaterialIcon name={active ? (descending ? "arrow_downward" : "arrow_upward") : "unfold_more"} />
  </button>;
}
