import type { UserOrdering, UserRoleFilter, UserStatusFilter } from "@second-pass/spl-api";
import type { FormEvent } from "react";

import { Button } from "../../../components/ui";
import { userRoleFilters } from "../usersListQuery";

export function UsersFiltersPageRegion({ search, role, isActive, ordering, advancedGroupsEnabled, onSearchChange, onSearch, onRoleChange, onStatusChange, onOrderingChange }: {
  search: string;
  role?: UserRoleFilter;
  isActive?: UserStatusFilter;
  ordering: UserOrdering;
  advancedGroupsEnabled: boolean;
  onSearchChange: (value: string) => void;
  onSearch: () => void;
  onRoleChange: (role?: UserRoleFilter) => void;
  onStatusChange: (status?: UserStatusFilter) => void;
  onOrderingChange: (ordering: UserOrdering) => void;
}) {
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); onSearch(); }
  const filters = userRoleFilters.filter(({ value }) => value !== "curator" || advancedGroupsEnabled);

  return <section className="users-controls" aria-label="User filters">
    <form className="users-search" role="search" onSubmit={submit}>
      <label htmlFor="users-search">Search</label>
      <input id="users-search" value={search} onChange={(event) => onSearchChange(event.target.value)} />
      <Button type="submit">Search</Button>
    </form>
    <div className="users-filter-row">
      <div className="users-role-filters" aria-label="Filter by role">
        {filters.map((filter) => <Button
          key={filter.value ?? "all"}
          type="button"
          aria-pressed={role === filter.value}
          onClick={() => onRoleChange(filter.value)}
        >{filter.label}</Button>)}
      </div>
      <div className="users-select-filters">
        <label>Status
          <select aria-label="Status" value={isActive ?? ""} onChange={(event) => onStatusChange((event.target.value || undefined) as UserStatusFilter | undefined)}>
            <option value="">All</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>
        </label>
        <label>Order
          <select aria-label="Ordering" value={ordering} onChange={(event) => onOrderingChange(event.target.value as UserOrdering)}>
            <option value="username">Username A-Z</option>
            <option value="-username">Username Z-A</option>
            <option value="name">Name A-Z</option>
            <option value="-name">Name Z-A</option>
            <option value="role">Role ascending</option>
            <option value="-role">Role descending</option>
            <option value="is_active">Status ascending</option>
            <option value="-is_active">Status descending</option>
          </select>
        </label>
      </div>
    </div>
  </section>;
}
