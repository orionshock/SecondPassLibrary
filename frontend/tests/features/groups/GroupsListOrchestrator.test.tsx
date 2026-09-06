/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, Outlet, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CurrentUser, LibraryGroup, Page, ServerInfo } from "@second-pass/spl-api";
import type { AppOutletContext } from "../../../src/app/layout/AppOrchestrator";
import { GroupsListOrchestrator } from "../../../src/features/groups/GroupsListOrchestrator";
import { buttonNamed, deferred, setControlValue, submit } from "../../support/domInteraction";

const sdk = vi.hoisted(() => ({ listGroups: vi.fn() }));
vi.mock("@second-pass/spl-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@second-pass/spl-api")>()),
  listGroups: sdk.listGroups,
}));

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const group = (id: string, name: string): LibraryGroup => ({ id, name, description: "", isPublicGroup: false, previewBooks: [] });
const page = (items: LibraryGroup[]): Page<LibraryGroup> => ({ items, count: items.length, next: null, previous: null });
const currentUser = {
  username: "manager", email: "", firstName: "", lastName: "", profileId: "manager", role: "manager",
  mustChangePassword: false, isOwner: false, isManager: true, isLibrarian: false, isReader: false,
  canAccessDjangoAdmin: false, groups: [{ id: "curated", name: "Curated", isPublicGroup: false, isCurator: true }],
} satisfies CurrentUser;
const serverInfo = { advancedLibraryGroupsEnabled: true } as ServerInfo;
let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
  vi.clearAllMocks();
});

async function mount(path = "/groups") {
  const container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  const context = { currentUser, serverInfo, refreshCurrentUser: vi.fn(), refreshServerInfo: vi.fn(), onCurrentUserChange: vi.fn(), setBreadcrumbs: vi.fn() } satisfies AppOutletContext;
  const router = createMemoryRouter([{ element: <Outlet context={context} />, children: [{ path: "/groups", element: <GroupsListOrchestrator /> }] }], { initialEntries: [path] });
  await act(async () => root?.render(<RouterProvider router={router} />));
  return { container, router };
}

describe("GroupsListOrchestrator", () => {
  it("loads the URL-backed query and submits a replacement search", async () => {
    sdk.listGroups.mockResolvedValue(page([group("curated", "Curated Readers")]));
    const { container } = await mount("/groups?q=old&page=2&page_size=30&ordering=-name");

    expect(sdk.listGroups).toHaveBeenCalledWith({ q: "old", ordering: "-name", includePreviewBooks: true, previewLimit: 12, page: 2, pageSize: 30 });
    expect(container.querySelector('a[href="/groups/curated"]')).not.toBeNull();
    expect(container.textContent).toContain("Curator");

    await act(async () => setControlValue(container.querySelector("#groups-search")!, "new query"));
    await act(async () => submit(container.querySelector('form[role="search"]')!));
    expect(sdk.listGroups).toHaveBeenLastCalledWith(expect.objectContaining({ q: "new query", page: 1 }));
  });

  it("retries a failed request", async () => {
    sdk.listGroups.mockRejectedValueOnce(new Error("Groups unavailable.")).mockResolvedValueOnce(page([group("recovered", "Recovered Group")]));
    const { container } = await mount();

    expect(container.querySelector('[role="alert"]')?.textContent).toContain("Groups unavailable.");
    await act(async () => buttonNamed(container, "Retry").click());

    expect(sdk.listGroups).toHaveBeenCalledTimes(2);
    expect(container.querySelector('a[href="/groups/recovered"]')).not.toBeNull();
  });

  it("does not allow an old query result to replace newer Groups", async () => {
    const oldRequest = deferred<Page<LibraryGroup>>();
    const newRequest = deferred<Page<LibraryGroup>>();
    sdk.listGroups.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise);
    const { container, router } = await mount("/groups?q=old");

    await act(async () => router.navigate("/groups?q=new"));
    await act(async () => newRequest.resolve(page([group("new", "New Group")])));
    await act(async () => oldRequest.resolve(page([group("old", "Old Group")])));

    expect(container.querySelector('a[href="/groups/new"]')).not.toBeNull();
    expect(container.querySelector('a[href="/groups/old"]')).toBeNull();
  });
});
