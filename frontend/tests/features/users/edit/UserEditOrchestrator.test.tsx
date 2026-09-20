/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, Outlet, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AssignableGroup, CurrentUser, ManagedUser, ServerInfo } from "@second-pass/spl-api";
import type { AppOutletContext } from "../../../../src/app/layout/AppOrchestrator";
import { UserEditOrchestrator } from "../../../../src/features/users/edit/UserEditOrchestrator";
import { buttonNamed, deferred, setControlValue, submit } from "../../../support/domInteraction";

const sdk = vi.hoisted(() => ({
  getUser: vi.fn(), listGroups: vi.fn(), updateUser: vi.fn(), resetPassword: vi.fn(),
  addMember: vi.fn(), updateMember: vi.fn(), removeMember: vi.fn(),
}));
vi.mock("@second-pass/spl-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@second-pass/spl-api")>()),
  getManagedUser: sdk.getUser,
  listAssignableGroupsForUser: sdk.listGroups,
  updateManagedUser: sdk.updateUser,
  resetManagedUserPassword: sdk.resetPassword,
  addGroupMember: sdk.addMember,
  updateGroupMember: sdk.updateMember,
  removeGroupMember: sdk.removeMember,
}));

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const owner: CurrentUser = {
  username: "owner", email: "", firstName: "", lastName: "", profileId: "owner-id", role: "manager",
  mustChangePassword: false, isOwner: true, isManager: false, isLibrarian: false, isReader: false,
  canAccessDjangoAdmin: false, groups: [],
};
const serverInfo: ServerInfo = {
  serverId: "server-id", serverUrls: [],
  name: "Library", description: "", bannerText: "", advancedLibraryGroupsEnabled: true,
  secondPassReaderWebClientUrl: null, marginaliaProfileUri: "profile", version: "dev", releaseDate: "",
  publicGroup: { id: "public", name: "Common Room", description: "" },
};
const bookClub = { id: "book-club", name: "Book Club", isPublicGroup: false, isCurator: false } as const;
const target = (id = "target", firstName = "Read"): ManagedUser => ({
  id, username: `reader-${id}`, firstName, lastName: "Er", email: "reader@example.test", role: "reader",
  isOwner: false, isActive: true, dateJoined: "now", lastLogin: null, mustChangePassword: false,
  groups: [{ id: "public", name: "Common Room", isPublicGroup: true, isCurator: false }, bookClub],
});
const availableGroup: AssignableGroup = { id: "new-group", name: "New Group", isPublicGroup: false };
let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

async function mount(path = "/users/target/edit") {
  const container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  const context = {
    currentUser: owner, serverInfo, refreshCurrentUser: vi.fn(), refreshServerInfo: vi.fn(),
    onCurrentUserChange: vi.fn(), setBreadcrumbs: vi.fn(),
  } satisfies AppOutletContext;
  const router = createMemoryRouter([{
    element: <Outlet context={context} />,
    children: [{ path: "/users/:profileId/edit", element: <UserEditOrchestrator /> }],
  }], { initialEntries: [path] });
  await act(async () => root?.render(<RouterProvider router={router} />));
  return { container, router };
}

function primeLoad(user = target(), groups: AssignableGroup[] = [availableGroup]) {
  sdk.getUser.mockResolvedValue(user);
  sdk.listGroups.mockResolvedValue(groups);
}

describe("UserEditOrchestrator", () => {
  it("loads account dependencies and reconciles a pending details save from the server response", async () => {
    primeLoad();
    const pending = deferred<ManagedUser>();
    sdk.updateUser.mockReturnValue(pending.promise);
    const { container } = await mount();
    const firstName = container.querySelector("#managed-user-first-name") as HTMLInputElement;
    act(() => {
      setControlValue(firstName, "Edited");
      setControlValue(container.querySelector("#managed-user-role")!, "librarian");
      setControlValue(container.querySelector("#managed-user-active")!, "inactive");
      submit(container.querySelector(".user-edit-form")!);
    });
    expect(sdk.updateUser).toHaveBeenCalledWith("target", expect.objectContaining({ firstName: "Edited", role: "librarian", isActive: false }));
    expect(buttonNamed(container, "Saving...").disabled).toBe(true);
    act(() => buttonNamed(container, "Saving...").click());
    expect(sdk.updateUser).toHaveBeenCalledOnce();

    await act(async () => pending.resolve(target("target", "Authoritative")));
    expect(firstName.value).toBe("Authoritative");
  });

  it("keeps the edited account draft available after a failed save", async () => {
    primeLoad();
    sdk.updateUser.mockRejectedValue(new Error("Save failed."));
    const { container } = await mount();
    const firstName = container.querySelector("#managed-user-first-name") as HTMLInputElement;
    act(() => setControlValue(firstName, "Recoverable"));

    await act(async () => submit(container.querySelector(".user-edit-form")!));

    expect(firstName.value).toBe("Recoverable");
    expect(container.querySelector('[role="alert"]')).not.toBeNull();
  });

  it("retries a failed dependency load and renders the recovered account", async () => {
    sdk.getUser.mockRejectedValueOnce(new Error("Load failed.")).mockResolvedValueOnce(target());
    sdk.listGroups.mockResolvedValue([availableGroup]);
    const { container } = await mount();
    expect(container.querySelector('[role="alert"]')).not.toBeNull();

    await act(async () => buttonNamed(container, "Retry").click());

    expect(sdk.getUser).toHaveBeenCalledTimes(2);
    expect(container.querySelector("#managed-user-first-name")).not.toBeNull();
  });

  it("gates password reset, refreshes account state after success, and exposes the one-time result", async () => {
    primeLoad();
    const confirm = vi.fn(() => false);
    vi.stubGlobal("confirm", confirm);
    sdk.resetPassword.mockResolvedValue({ username: "reader-target", temporaryPassword: "reset-secret", message: "Reset" });
    const { container } = await mount();

    await act(async () => buttonNamed(container, "Reset password").click());
    expect(sdk.resetPassword).not.toHaveBeenCalled();
    confirm.mockReturnValue(true);
    await act(async () => buttonNamed(container, "Reset password").click());

    expect(sdk.resetPassword).toHaveBeenCalledWith("target");
    expect(sdk.getUser).toHaveBeenCalledTimes(2);
    expect((container.querySelector("#managed-user-temporary-password") as HTMLTextAreaElement).value).toContain("reset-secret");
  });

  it("adds a Group membership and refreshes both account and assignable Groups", async () => {
    primeLoad();
    sdk.addMember.mockResolvedValue(undefined);
    const { container } = await mount();
    const curator = Array.from(container.querySelectorAll<HTMLInputElement>('input[type="checkbox"]')).find((input) => input.parentElement?.textContent?.includes("Grant curator"));
    act(() => curator?.click());

    await act(async () => submit(container.querySelector(".user-membership-add")!));

    expect(sdk.addMember).toHaveBeenCalledWith("new-group", { userId: "target", isCurator: true });
    expect(sdk.getUser).toHaveBeenCalledTimes(2);
    expect(sdk.listGroups).toHaveBeenCalledTimes(2);
  });

  it("preserves membership state when confirmed removal fails", async () => {
    primeLoad();
    sdk.removeMember.mockRejectedValue(new Error("Removal failed."));
    vi.stubGlobal("confirm", vi.fn(() => true));
    const { container } = await mount();

    await act(async () => buttonNamed(container, "Remove Book Club").click());

    expect(sdk.removeMember).toHaveBeenCalledWith("book-club", "target");
    expect(container.querySelector('[aria-label="Remove Book Club"]')).not.toBeNull();
    expect(container.querySelector('[role="alert"]')).not.toBeNull();
  });

  it("ignores an old account response after navigation selects another identity", async () => {
    const oldRequest = deferred<ManagedUser>();
    const newRequest = deferred<ManagedUser>();
    sdk.getUser.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise);
    sdk.listGroups.mockResolvedValue([]);
    const { container, router } = await mount("/users/old/edit");

    await act(async () => router.navigate("/users/new/edit"));
    await act(async () => newRequest.resolve(target("new", "New")));
    await act(async () => oldRequest.resolve(target("old", "Old")));

    expect((container.querySelector("#managed-user-first-name") as HTMLInputElement).value).toBe("New");
    expect(container.textContent).not.toContain("reader-old");
  });
});
