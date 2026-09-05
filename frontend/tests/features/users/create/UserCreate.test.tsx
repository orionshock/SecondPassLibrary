import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { ApiError, type CreateUserResult, type CurrentUser, type ServerInfo } from "@second-pass/spl-api";
import { AppOrchestrator } from "../../../../src/app/layout/AppOrchestrator";
import { UserCreateFormPageRegion } from "../../../../src/features/users/create/UserCreateFormPageRegion";
import { UserCreateSuccessPageRegion } from "../../../../src/features/users/create/UserCreateSuccessPageRegion";
import { createUserInputFromDraft, emptyUserCreateDraft } from "../../../../src/features/users/create/userCreateForm";
import { creatableUserRoles } from "../../../../src/features/users/userCreateRoles";
import { usersCreateBreadcrumbFallback, usersListBreadcrumbFallback } from "../../../../src/features/users/usersBreadcrumbs";
import { UsersListOrchestrator } from "../../../../src/features/users/list/UsersListOrchestrator";

const owner: CurrentUser = {
  username: "owner", email: "", firstName: "", lastName: "", profileId: "owner-id", role: "manager",
  mustChangePassword: false, isOwner: true, isManager: false, isLibrarian: false, isReader: false, canAccessDjangoAdmin: false, groups: [],
};
const manager: CurrentUser = { ...owner, username: "manager", profileId: "manager-id", isOwner: false, isManager: true };
const server: ServerInfo = { name: "Library", description: "", bannerText: "", advancedLibraryGroupsEnabled: false, secondPassReaderWebClientUrl: null, marginaliaProfileUri: "profile", publicGroup: { id: "public", name: "Common Room", description: "" }, version: "dev", releaseDate: "" };

function renderForm(user: CurrentUser, error?: Error): string {
  return renderToStaticMarkup(<MemoryRouter><UserCreateFormPageRegion
    draft={emptyUserCreateDraft}
    roles={creatableUserRoles(user)}
    state={{ pending: false, error }}
    onChange={vi.fn()}
    onSubmit={vi.fn()}
  /></MemoryRouter>);
}

describe("User create workflow", () => {
  it("shows capitalized Owner role choices and defaults to Reader without an Active field", () => {
    const markup = renderForm(owner);
    expect(creatableUserRoles(owner)).toEqual(["manager", "librarian", "reader"]);
    expect(markup).toContain('<option value="manager">Manager</option>');
    expect(markup).toContain('<option value="librarian">Librarian</option>');
    expect(markup).toContain('<option value="reader" selected="">Reader</option>');
    expect(markup).not.toContain('value="owner"');
    expect(markup).not.toContain('type="checkbox"');
    expect(markup).toContain('class="form-field"');
  });

  it("limits Manager choices to Librarian and Reader", () => {
    const markup = renderForm(manager);
    expect(creatableUserRoles(manager)).toEqual(["librarian", "reader"]);
    expect(markup).not.toContain('value="manager"');
    expect(markup).toContain("Librarian");
    expect(markup).toContain("Reader");
  });

  it("submits only create fields and returns Cancel to the Users base route", () => {
    expect(createUserInputFromDraft({ username: "new", email: "e@example.test", firstName: "First", lastName: "Last", role: "reader" })).toEqual({
      username: "new", email: "e@example.test", firstName: "First", lastName: "Last", role: "reader",
    });
    const markup = renderForm(owner);
    expect(markup).toMatch(/<a class="button button--secondary" href="\/users"[^>]*>Cancel<\/a>/);
  });

  it("renders field and bounded action feedback from validation errors", () => {
    const markup = renderForm(owner, new ApiError("Invalid user.", 400, { fields: { username: ["Already exists."] } }));
    expect(markup).toContain("Already exists.");
    expect(markup).toContain('role="alert"');
  });

  it("shows the one-time temporary password warning and onward actions", () => {
    const result: CreateUserResult = {
      user: {
        id: "created-id", username: "new-reader", email: "", firstName: "New", lastName: "Reader", role: "reader",
        isOwner: false, isActive: true, dateJoined: "2026-07-20T00:00:00Z", lastLogin: null, mustChangePassword: true, groups: [],
      },
      temporaryPassword: "one-time-secret",
      message: "Show this password now.",
    };
    const markup = renderToStaticMarkup(<MemoryRouter><UserCreateSuccessPageRegion result={result} /></MemoryRouter>);
    expect(markup).toContain("Temporary credentials");
    expect(markup).toContain('aria-label="User new-reader"');
    expect(markup).not.toContain("@new-reader");
    expect(markup).toContain("Username: new-reader");
    expect(markup).toContain("Password: one-time-secret");
    expect(markup).toContain("one-time-secret");
    expect(markup).toContain("It will not be shown again");
    expect(markup).toContain('readOnly=""');
    expect(markup.indexOf("one-time-secret")).toBeLessThan(markup.indexOf("It will not be shown again"));
    expect(markup).toContain("check_circle");
    expect(markup).toContain('href="/users/created-id/edit"');
  });

  it("links the Users list action to create and keeps breadcrumb ownership on the child route", () => {
    const markup = renderToStaticMarkup(<MemoryRouter initialEntries={["/users"]}><Routes><Route element={<AppOrchestrator user={owner} server={server} onCurrentUserChange={vi.fn()} />}><Route path="users" element={<UsersListOrchestrator />} /></Route></Routes></MemoryRouter>);
    expect(markup).toContain('href="/users/new"');
    expect(usersListBreadcrumbFallback).toEqual([]);
    expect(usersCreateBreadcrumbFallback).toEqual([{ label: "Users", to: "/users", resetTrail: true, icon: "user" }, { label: "New" }]);
  });
});

