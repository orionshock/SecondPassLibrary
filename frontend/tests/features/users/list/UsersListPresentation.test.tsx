import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import type { ManagedUser, Page } from "@second-pass/spl-api";
import { UsersFiltersPageRegion } from "../../../../src/features/users/list/UsersFiltersPageRegion";
import { UsersListPageRegion } from "../../../../src/features/users/list/UsersListPageRegion";
import { usersListBreadcrumbFallback } from "../../../../src/features/users/usersBreadcrumbs";

const owner: ManagedUser = {
  id: "owner-id", username: "owner", firstName: "Ada", lastName: "Lovelace", email: "ada@example.test",
  role: "manager", isOwner: true, isActive: false, dateJoined: "2026-01-01T00:00:00Z", lastLogin: null,
  mustChangePassword: false, groups: [
    { id: "public", name: "Common Room", isPublicGroup: true, isCurator: false },
    { id: "group", name: "Editors", isPublicGroup: false, isCurator: true },
  ],
};

function renderList(page?: Page<ManagedUser>, options: { loading?: boolean; error?: Error; advanced?: boolean } = {}) {
  return renderToStaticMarkup(<MemoryRouter><UsersListPageRegion
    page={page}
    pageNumber={1}
    pageSize={20}
    ordering="username"
    advancedGroupsEnabled={options.advanced ?? false}
    loading={options.loading ?? false}
    error={options.error}
    onOrderingChange={vi.fn()}
    onPageChange={vi.fn()}
    onPageSizeChange={vi.fn()}
    onRetry={vi.fn()}
  /></MemoryRouter>);
}

describe("Users list regions", () => {
  it("renders effective Owner role, inactive state, and the Edit destination", () => {
    const markup = renderList({ items: [owner], count: 1, next: null, previous: null }, { advanced: true });
    expect(markup).toContain("Ada Lovelace");
    expect(markup).toContain('aria-label="User owner"');
    expect(markup).not.toContain("@owner");
    expect(markup).toContain("ada@example.test");
    expect(markup).toContain("Owner");
    expect(markup).toContain("Inactive");
    expect(markup).toContain('href="/users/owner-id/edit"');
    expect(markup).toContain('aria-label="Edit owner"');
  });

  it("renders group membership and curator facts in advanced mode", () => {
    const markup = renderList({ items: [owner], count: 1, next: null, previous: null }, { advanced: true });
    expect(markup).toContain('aria-label="Groups"');
    expect(markup).toContain("Common Room");
    expect(markup).toContain('aria-label="Curates"');
    expect(markup).toContain("Editors");
  });

  it("omits status treatment for active users", () => {
    const markup = renderList({ items: [{ ...owner, isActive: true, mustChangePassword: true }], count: 1, next: null, previous: null }, { advanced: true });
    expect(markup).not.toContain(">Active<");
    expect(markup).not.toContain("Password change required");
  });

  it("shows page size 20 as the selected default", () => {
    const markup = renderList({ items: [owner], count: 1, next: null, previous: null });
    expect(markup).toContain('aria-label="Users pagination, top"');
    expect(markup).toContain('aria-label="Users pagination, bottom"');
    expect(markup).toContain('<option value="20" selected="">20</option>');
    expect(markup).toContain('<option value="200">200</option>');
  });

  it("renders bounded loading, empty, and retryable error states", () => {
    expect(renderList(undefined, { loading: true })).toContain('aria-busy="true"');
    expect(renderList({ items: [], count: 0, next: null, previous: null })).toContain("No users match");
    const errorMarkup = renderList(undefined, { error: new Error("Unavailable") });
    expect(errorMarkup).toContain('role="alert"');
    expect(errorMarkup).toContain("Retry");
  });

  it("renders role filters in product order and hides Curator in simple mode", () => {
    const renderFilters = (advancedGroupsEnabled: boolean, operatorIsOwner = true) => renderToStaticMarkup(<UsersFiltersPageRegion
      search=""
      advancedGroupsEnabled={advancedGroupsEnabled}
      operatorIsOwner={operatorIsOwner}
      onSearchChange={vi.fn()}
      onSearch={vi.fn()}
      onRoleChange={vi.fn()}
      onStatusChange={vi.fn()}
    />);
    const advanced = renderFilters(true);
    const labels = ["All", "Reader", "Curator", "Librarian", "Manager", "Owner"];
    labels.slice(1).forEach((label, index) => expect(advanced.indexOf(labels[index]!)).toBeLessThan(advanced.indexOf(label)));
    expect(renderFilters(false)).not.toContain("Curator");
    expect(advanced).not.toContain('aria-label="Ordering"');
    const manager = renderFilters(true, false);
    expect(manager).not.toContain(">Owner</button>");
    expect(manager).toContain(">Manager</button>");
  });

  it("uses no breadcrumb on the base Users route", () => {
    expect(usersListBreadcrumbFallback).toEqual([]);
  });
});
