/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, Outlet, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CompactBook, CurrentUser, GroupMembership, LibraryGroup, Page, ServerInfo, ShelfSummary } from "@second-pass/spl-api";
import type { AppOutletContext } from "../../../../src/app/layout/AppOrchestrator";
import { GroupDetailOrchestrator } from "../../../../src/features/groups/detail/GroupDetailOrchestrator";
import { buttonNamed, deferred } from "../../../support/domInteraction";

const sdk = vi.hoisted(() => ({ getGroup: vi.fn(), listGroupBooks: vi.fn(), listGroupMembers: vi.fn(), listShelves: vi.fn() }));
vi.mock("@second-pass/spl-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@second-pass/spl-api")>()),
  getGroup: sdk.getGroup,
  listGroupBooks: sdk.listGroupBooks,
  listGroupMembers: sdk.listGroupMembers,
  listShelves: sdk.listShelves,
}));

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const group = (id: string, name: string): LibraryGroup => ({ id, name, description: "", isPublicGroup: false, previewBooks: [] });
const book = (id: string, title: string): CompactBook => ({
  id, title, sortTitle: title, subtitle: "", authors: [], series: null, catalogTags: [], language: "", publisher: "",
  publishedYear: null, publishedMonth: null, publishedDay: null, publishedDatePrecision: "", coverUrl: null, fileFormat: "epub",
});
const page = <T,>(items: T[]): Page<T> => ({ items, count: items.length, next: null, previous: null });
const currentUser = {
  username: "manager", email: "", firstName: "", lastName: "", profileId: "manager", role: "manager",
  mustChangePassword: false, isOwner: false, isManager: true, isLibrarian: false, isReader: false,
  canAccessDjangoAdmin: false, groups: [{ id: "group-one", name: "Group One", isPublicGroup: false, isCurator: true }],
} satisfies CurrentUser;
const serverInfo = { advancedLibraryGroupsEnabled: true } as ServerInfo;
let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
  vi.clearAllMocks();
});

function prime() {
  sdk.getGroup.mockResolvedValue(group("group-one", "Group One"));
  sdk.listGroupBooks.mockResolvedValue(page([book("book-one", "Book One")]));
  sdk.listGroupMembers.mockResolvedValue(page<GroupMembership>([]));
  sdk.listShelves.mockResolvedValue(page<ShelfSummary>([]));
}

async function mount(path = "/groups/group-one") {
  const container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  const context = { currentUser, serverInfo, refreshCurrentUser: vi.fn(), refreshServerInfo: vi.fn(), onCurrentUserChange: vi.fn(), setBreadcrumbs: vi.fn() } satisfies AppOutletContext;
  const router = createMemoryRouter([{ element: <Outlet context={context} />, children: [{ path: "/groups/:groupId", element: <GroupDetailOrchestrator /> }] }], { initialEntries: [path] });
  await act(async () => root?.render(<RouterProvider router={router} />));
  return { container, router };
}

describe("GroupDetailOrchestrator", () => {
  it("loads Group identity and the URL-selected Book page", async () => {
    prime();
    const { container } = await mount("/groups/group-one?q=storm&page=2&page_size=30&ordering=-author");

    expect(sdk.getGroup).toHaveBeenCalledWith("group-one", { includePreviewBooks: true });
    expect(sdk.listGroupBooks).toHaveBeenCalledWith("group-one", { q: "storm", ordering: "-author", page: 2, pageSize: 30 });
    expect(container.querySelector('a[href="/library/books/book-one"]')).not.toBeNull();
    expect(container.querySelector('a[href="/groups/group-one/edit"]')).not.toBeNull();
  });

  it("loads only the newly selected relationship tab", async () => {
    prime();
    const { container } = await mount();

    await act(async () => buttonNamed(container, "Members").click());
    expect(sdk.listGroupMembers).toHaveBeenCalledWith("group-one", { page: 1, pageSize: 20 });
    expect(sdk.listShelves).not.toHaveBeenCalled();

    await act(async () => buttonNamed(container, "Shelves").click());
    expect(sdk.listShelves).toHaveBeenCalledWith(expect.objectContaining({ scope: "group", ownerGroupId: "group-one", page: 1 }));
  });

  it("retries detail and selected-page failures independently", async () => {
    sdk.getGroup.mockRejectedValueOnce(new Error("Group unavailable.")).mockResolvedValueOnce(group("group-one", "Recovered Group"));
    sdk.listGroupBooks.mockRejectedValueOnce(new Error("Books unavailable.")).mockResolvedValueOnce(page([book("recovered", "Recovered Book")]));
    const { container } = await mount();

    await act(async () => buttonNamed(container, "Retry").click());
    expect(container.textContent).toContain("Books unavailable.");
    await act(async () => buttonNamed(container, "Retry").click());

    expect(sdk.getGroup).toHaveBeenCalledTimes(2);
    expect(sdk.listGroupBooks).toHaveBeenCalledTimes(2);
    expect(container.querySelector('a[href="/library/books/recovered"]')).not.toBeNull();
  });

  it("does not let the previous route identity replace the current Group", async () => {
    const oldRequest = deferred<LibraryGroup>();
    const newRequest = deferred<LibraryGroup>();
    sdk.getGroup.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise);
    sdk.listGroupBooks.mockResolvedValue(page<CompactBook>([]));
    const { container, router } = await mount();

    await act(async () => router.navigate("/groups/group-two"));
    expect(sdk.getGroup).toHaveBeenLastCalledWith("group-two", { includePreviewBooks: true });
    await act(async () => newRequest.resolve(group("group-two", "Group Two")));
    await act(async () => oldRequest.resolve(group("group-one", "Group One")));

    expect(container.textContent).toContain("Group Two");
    expect(container.textContent).not.toContain("Group One");
  });
});
