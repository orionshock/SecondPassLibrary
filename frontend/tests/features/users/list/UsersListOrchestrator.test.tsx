/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, Outlet, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CurrentUser, ManagedUser, Page, ServerInfo } from "@second-pass/spl-api";
import type { AppOutletContext } from "../../../../src/app/layout/AppOrchestrator";
import { UsersListOrchestrator } from "../../../../src/features/users/list/UsersListOrchestrator";
import { buttonNamed, deferred, setControlValue, submit } from "../../../support/domInteraction";

const sdk = vi.hoisted(() => ({ listUsers: vi.fn() }));
vi.mock("@second-pass/spl-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@second-pass/spl-api")>()),
  listUsers: sdk.listUsers,
}));

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const operator: CurrentUser = {
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
const managedUser = (id: string, username: string): ManagedUser => ({
  id, username, firstName: "", lastName: "", email: `${username}@example.test`, role: "reader",
  isOwner: false, isActive: true, dateJoined: "now", lastLogin: null, mustChangePassword: false, groups: [],
});
const page = (items: ManagedUser[]): Page<ManagedUser> => ({ items, count: items.length, next: null, previous: null });
let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
  vi.clearAllMocks();
});

async function mount(path = "/users") {
  const container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  const context = {
    currentUser: operator, serverInfo, refreshCurrentUser: vi.fn(), refreshServerInfo: vi.fn(),
    onCurrentUserChange: vi.fn(), setBreadcrumbs: vi.fn(),
  } satisfies AppOutletContext;
  const router = createMemoryRouter([{
    element: <Outlet context={context} />,
    children: [{ path: "/users", element: <UsersListOrchestrator /> }],
  }], { initialEntries: [path] });
  await act(async () => root?.render(<RouterProvider router={router} />));
  return { container, router };
}

describe("UsersListOrchestrator", () => {
  it("loads URL-backed filters and issues new requests when search and status change", async () => {
    sdk.listUsers.mockResolvedValue(page([managedUser("one", "ada")]));
    const { container } = await mount("/users?q=ada&role=reader&is_active=true&page=2&page_size=50");

    expect(sdk.listUsers).toHaveBeenCalledWith({ q: "ada", role: "reader", isActive: "true", ordering: "role", page: 2, pageSize: 50 });
    act(() => {
      setControlValue(container.querySelector("#users-search")!, "grace");
      submit(container.querySelector('[role="search"]')!);
    });
    await act(async () => undefined);
    expect(sdk.listUsers).toHaveBeenLastCalledWith(expect.objectContaining({ q: "grace", page: 1 }));

    act(() => setControlValue(container.querySelector('[aria-label="Status"]')!, "false"));
    await act(async () => undefined);
    expect(sdk.listUsers).toHaveBeenLastCalledWith(expect.objectContaining({ q: "grace", isActive: "false", page: 1 }));
  });

  it("retries a failed initial request and renders the recovered authoritative page", async () => {
    sdk.listUsers.mockRejectedValueOnce(new Error("Users unavailable.")).mockResolvedValueOnce(page([managedUser("two", "recovered")]));
    const { container } = await mount();
    expect(container.querySelector('[role="alert"]')).not.toBeNull();

    await act(async () => buttonNamed(container, "Retry").click());

    expect(sdk.listUsers).toHaveBeenCalledTimes(2);
    expect(container.querySelector('[aria-label="Edit recovered"]')).not.toBeNull();
  });

  it("does not allow an older query response to replace newer search results", async () => {
    const oldRequest = deferred<Page<ManagedUser>>();
    const newRequest = deferred<Page<ManagedUser>>();
    sdk.listUsers.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise);
    const { container, router } = await mount("/users?q=old");

    await act(async () => router.navigate("/users?q=new"));
    await act(async () => newRequest.resolve(page([managedUser("new", "new-result")])));
    await act(async () => oldRequest.resolve(page([managedUser("old", "old-result")])));

    expect(container.querySelector('[aria-label="Edit new-result"]')).not.toBeNull();
    expect(container.querySelector('[aria-label="Edit old-result"]')).toBeNull();
  });
});
