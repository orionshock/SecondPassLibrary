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
  it("renders mapped server results with effective Owner role and inactive styling", () => {
    const markup = renderList({ items: [owner], count: 1, next: null, previous: null }, { advanced: true });
    expect(markup).toContain("ada@example.test");
    expect(markup).toContain("Owner");
    expect(markup).toContain("users-row--inactive");
    expect(markup).toContain("users-status-pill--inactive");
    expect(markup).toContain('<td class="users-memberships"><div class="users-memberships__content">');
    expect(markup).not.toContain('<td class="users-memberships" style="display:grid">');
    expect(markup).toContain('class="badge badge--success"');
    expect(markup).toContain('aria-label="Curates"><span class="badge badge--accent">Editors</span>');
    expect(markup).toContain('<td class="users-row-actions"><a class="icon-button"');
    expect(markup).toContain('href="/users/owner-id/edit"');
  });

  it("renders grouped identity, role/status, memberships, and action columns", () => {
    const markup = renderList({ items: [owner], count: 1, next: null, previous: null }, { advanced: true });
    const headings = ["Name", "Username", "Email", "Role", "Status", "Last login", "Groups / Curates", "Actions"];
    headings.slice(1).forEach((heading, index) => expect(markup.indexOf(headings[index]!)).toBeLessThan(markup.indexOf(heading)));
    expect(markup).toContain('<td class="users-identity"><div class="users-identity__primary"><span class="material-symbols-outlined material-icon"');
    expect(markup).toContain("Ada Lovelace</strong><span class=\"users-identity__dot\"");
    expect(markup).toContain("&lt;@owner&gt;</span></div><div class=\"users-identity__email\">ada@example.test</div></td>");
    expect(markup).toContain('<td class="users-role-status"><div class="users-role-status__content"><span class="badge badge--accent">Owner</span><span class="users-status-pill users-status-pill--inactive">Inactive</span></div></td>');
    expect(markup).toContain('aria-label="Groups"><span class="badge badge--success"');
    expect(markup).not.toContain('aria-label="Groups"><span class="badge badge--default">Editors</span>');
  });

  it("omits status treatment for active users", () => {
    const markup = renderList({ items: [{ ...owner, isActive: true, mustChangePassword: true }], count: 1, next: null, previous: null }, { advanced: true });
    expect(markup).not.toContain("users-status-pill");
    expect(markup).not.toContain(">Active<");
    expect(markup).not.toContain("Password change required");
  });

  it("shows page size 20 as the selected default", () => {
    const markup = renderList({ items: [owner], count: 1, next: null, previous: null });
    expect(markup).toContain('<option value="20" selected="">20</option>');
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
      advancedGroupsEnabled={advancedGroupsEnabled}
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
  });

  it("uses no breadcrumb on the base Users route", () => {
    expect(usersListBreadcrumbFallback).toEqual([]);
  });
});
