import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { ManagedUser, Page } from "@second-pass/spl-api";
import { UsersFiltersPageRegion } from "../features/users/regions/UsersFiltersPageRegion";
import { UsersListPageRegion } from "../features/users/regions/UsersListPageRegion";
import { usersListBreadcrumbFallback } from "../features/users/usersBreadcrumbs";

const owner: ManagedUser = {
  id: "owner-id", username: "owner", firstName: "Ada", lastName: "Lovelace", email: "ada@example.test",
  role: "manager", isOwner: true, isActive: false, dateJoined: "2026-01-01T00:00:00Z", lastLogin: null,
  mustChangePassword: false, groups: [{ id: "group", name: "Editors", isPublicGroup: false, isCurator: true }],
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
  it("renders mapped server results with effective Owner role and inactive styling", () => {
    const markup = renderList({ items: [owner], count: 1, next: null, previous: null }, { advanced: true });
    expect(markup).toContain("ada@example.test");
    expect(markup).toContain("Owner");
    expect(markup).toContain("users-row--inactive");
    expect(markup).toContain("users-status-pill--inactive");
    expect(markup).toContain("Curates: Editors");
    expect(markup).toContain('href="/users/owner-id/edit"');
  });

  it("renders bounded loading, empty, and retryable error states", () => {
    expect(renderList(undefined, { loading: true })).toContain('aria-busy="true"');
    expect(renderList({ items: [], count: 0, next: null, previous: null })).toContain("No users match");
    const errorMarkup = renderList(undefined, { error: new Error("Unavailable") });
    expect(errorMarkup).toContain('role="alert"');
    expect(errorMarkup).toContain("Retry");
  });

  it("renders role filters in product order and hides Curator in simple mode", () => {
    const renderFilters = (advancedGroupsEnabled: boolean) => renderToStaticMarkup(<UsersFiltersPageRegion
      search=""
      ordering="username"
      advancedGroupsEnabled={advancedGroupsEnabled}
      onSearchChange={vi.fn()}
      onSearch={vi.fn()}
      onRoleChange={vi.fn()}
      onStatusChange={vi.fn()}
      onOrderingChange={vi.fn()}
    />);
    const advanced = renderFilters(true);
    const labels = ["All", "Reader", "Curator", "Librarian", "Manager", "Owner"];
    labels.slice(1).forEach((label, index) => expect(advanced.indexOf(labels[index]!)).toBeLessThan(advanced.indexOf(label)));
    expect(renderFilters(false)).not.toContain("Curator");
  });

  it("uses no breadcrumb on the base Users route", () => {
    expect(usersListBreadcrumbFallback).toEqual([]);
  });
});
