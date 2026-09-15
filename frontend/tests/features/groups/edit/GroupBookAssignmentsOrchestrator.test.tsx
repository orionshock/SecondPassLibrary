/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, Outlet, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, type CompactBook, type CurrentUser, type LibraryGroup, type ServerInfo } from "@second-pass/spl-api";
import type { AppOutletContext } from "../../../../src/app/layout/AppOrchestrator";
import { GroupEditOrchestrator } from "../../../../src/features/groups/edit/GroupEditOrchestrator";
import { buttonNamed, deferred, setControlValue, submit } from "../../../support/domInteraction";

const sdk = vi.hoisted(() => ({
  getGroup: vi.fn(), updateGroup: vi.fn(), deleteGroup: vi.fn(),
  listBooks: vi.fn(), searchBooks: vi.fn(), addBook: vi.fn(), removeBook: vi.fn(),
  listMembers: vi.fn(), listChoices: vi.fn(), addMember: vi.fn(), updateMember: vi.fn(), removeMember: vi.fn(),
}));
vi.mock("@second-pass/spl-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@second-pass/spl-api")>()),
  getGroup: sdk.getGroup,
  updateGroup: sdk.updateGroup,
  deleteGroup: sdk.deleteGroup,
  listGroupBooks: sdk.listBooks,
  searchLibraryBooks: sdk.searchBooks,
  addBookToGroup: sdk.addBook,
  removeBookFromGroup: sdk.removeBook,
  listGroupMembers: sdk.listMembers,
  listUserChoices: sdk.listChoices,
  addGroupMember: sdk.addMember,
  updateGroupMember: sdk.updateMember,
  removeGroupMember: sdk.removeMember,
}));

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const group: LibraryGroup = { id: "group/id", name: "Readers", description: "", isPublicGroup: false };
const assignedBook: CompactBook = {
  id: "book-one", title: "Assigned Book", sortTitle: "Assigned Book", subtitle: "", authors: [],
  series: null, catalogTags: [], language: "", publisher: "", publishedYear: null,
  publishedMonth: null, publishedDay: null, publishedDatePrecision: "", coverUrl: null, fileFormat: "epub",
};
const candidateBook: CompactBook = { ...assignedBook, id: "book-two", title: "Candidate Book", sortTitle: "Candidate Book" };
const manager = {
  username: "manager", email: "", firstName: "", lastName: "", profileId: "profile",
  role: "manager", mustChangePassword: false, isOwner: false, isManager: true,
  isLibrarian: false, isReader: false, canAccessDjangoAdmin: false, groups: [],
} satisfies CurrentUser;
const serverInfo = {
  name: "Library", description: "", bannerText: "", advancedLibraryGroupsEnabled: true,
  secondPassReaderWebClientUrl: null, marginaliaProfileUri: "profile", version: "dev",
  releaseDate: "", publicGroup: { id: "public", name: "Common Room", description: "" },
} satisfies ServerInfo;
const page = (items: CompactBook[], count = items.length) => ({ items, count, next: null, previous: null });
let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

async function mount(path: string, currentUser: CurrentUser = manager) {
  const container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  const context = {
    currentUser, serverInfo, refreshCurrentUser: vi.fn(), refreshServerInfo: vi.fn(),
    onCurrentUserChange: vi.fn(), setBreadcrumbs: vi.fn(),
  } satisfies AppOutletContext;
  const router = createMemoryRouter([{
    element: <Outlet context={context} />,
    children: [{ path: "/groups/:groupId/edit", element: <GroupEditOrchestrator /> }],
  }], { initialEntries: [path] });
  await act(async () => root?.render(<RouterProvider router={router} />));
  return { container, router };
}

describe("GroupEditOrchestrator Book assignments", () => {
  it("freezes Group metadata during save and preserves the submitted draft after failure", async () => {
    sdk.getGroup.mockResolvedValue(group);
    const pending = deferred<LibraryGroup>();
    sdk.updateGroup.mockReturnValueOnce(pending.promise).mockResolvedValueOnce({ ...group, name: "Edited Readers" });
    const { container } = await mount("/groups/group%2Fid/edit");
    const nameInput = container.querySelector<HTMLInputElement>("#group-name")!;

    await act(async () => setControlValue(nameInput, "Edited Readers"));
    act(() => submit(container.querySelector<HTMLFormElement>(".group-metadata-form")!));

    expect(nameInput.disabled).toBe(true);
    expect(buttonNamed(container, "Saving...").disabled).toBe(true);
    await act(async () => setControlValue(nameInput, "Newer Readers"));
    expect(nameInput.value).toBe("Edited Readers");
    act(() => submit(container.querySelector<HTMLFormElement>(".group-metadata-form")!));
    expect(sdk.updateGroup).toHaveBeenCalledOnce();

    await act(async () => pending.reject(new Error("Group save failed.")));
    expect(nameInput.disabled).toBe(false);
    expect(nameInput.value).toBe("Edited Readers");
    expect(container.querySelector("[role=\"alert\"]")).not.toBeNull();

    await act(async () => submit(container.querySelector<HTMLFormElement>(".group-metadata-form")!));
    expect(sdk.updateGroup).toHaveBeenCalledTimes(2);
  });

  it("removes a confirmed Book, locks conflicting actions, and refreshes the assigned list", async () => {
    sdk.getGroup.mockResolvedValue(group);
    sdk.listBooks.mockResolvedValueOnce(page([assignedBook])).mockResolvedValueOnce(page([]));
    const pending = deferred<void>();
    sdk.removeBook.mockReturnValue(pending.promise);
    vi.stubGlobal("confirm", vi.fn(() => true));
    const { container, router } = await mount("/groups/group%2Fid/edit?tab=books");

    act(() => buttonNamed(container, "Remove Assigned Book from group").click());
    expect(sdk.removeBook).toHaveBeenCalledWith("group/id", "book-one");
    expect(buttonNamed(container, "Remove Assigned Book from group").disabled).toBe(true);

    await act(async () => pending.resolve());
    expect(sdk.listBooks).toHaveBeenCalledTimes(2);
    expect(container.textContent).not.toContain("Assigned Book");
    expect(router.state.location.search).toBe("?tab=books");
  });

  it("recovers assigned Books to the last valid URL page after final-page removal", async () => {
    sdk.getGroup.mockResolvedValue(group);
    sdk.listBooks
      .mockResolvedValueOnce({ ...page([assignedBook], 31), previous: "page-1" })
      .mockRejectedValueOnce(new ApiError("Invalid page.", 404))
      .mockResolvedValue(page([{ ...assignedBook, id: "remaining", title: "Remaining Book" }], 30));
    sdk.removeBook.mockResolvedValue(undefined);
    vi.stubGlobal("confirm", vi.fn(() => true));
    const { container, router } = await mount(
      "/groups/group%2Fid/edit?trail=context&tab=books&page=2&page_size=30",
    );

    await act(async () => buttonNamed(container, "Remove Assigned Book from group").click());

    expect(sdk.listBooks.mock.calls.map(([, query]) => query.page)).toEqual([2, 2, 1, 1]);
    expect(router.state.location.search).toBe("?trail=context&tab=books&page_size=30");
    expect(router.state.historyAction).toBe("REPLACE");
    expect(container.textContent).toContain("Remaining Book");
    expect(container.querySelector("[role=\"alert\"]")).toBeNull();
  });

  it("keeps an assigned Book visible when removal fails", async () => {
    sdk.getGroup.mockResolvedValue(group);
    sdk.listBooks.mockResolvedValue(page([assignedBook]));
    sdk.removeBook.mockRejectedValue(new Error("Book assignment failed."));
    vi.stubGlobal("confirm", vi.fn(() => true));
    const { container } = await mount("/groups/group%2Fid/edit?tab=books");

    await act(async () => buttonNamed(container, "Remove Assigned Book from group").click());

    expect(container.textContent).toContain("Assigned Book");
    expect(container.querySelector("[role=\"alert\"]")).not.toBeNull();
    expect(sdk.listBooks).toHaveBeenCalledOnce();
  });

  it("adds a searched Book and refreshes the authoritative candidate population", async () => {
    sdk.getGroup.mockResolvedValue(group);
    sdk.searchBooks.mockResolvedValueOnce(page([candidateBook])).mockResolvedValueOnce(page([]));
    sdk.addBook.mockResolvedValue(undefined);
    const { container } = await mount("/groups/group%2Fid/edit?tab=add-books");

    await act(async () => setControlValue(container.querySelector<HTMLInputElement>("#group-add-books-search")!, "Candidate"));
    await act(async () => submit(container.querySelector<HTMLFormElement>('form[role="search"]')!));
    await act(async () => buttonNamed(container, "Add").click());

    expect(sdk.addBook).toHaveBeenCalledWith("group/id", "book-two");
    expect(sdk.searchBooks).toHaveBeenCalledTimes(2);
    expect(container.textContent).not.toContain("Candidate Book");
  });

  it("does not let a superseded candidate search replace the newer result", async () => {
    sdk.getGroup.mockResolvedValue(group);
    const oldSearch = deferred<ReturnType<typeof page>>();
    sdk.searchBooks.mockImplementation(({ q }: { q: string }) => q === "Old"
      ? oldSearch.promise
      : Promise.resolve(page([{ ...candidateBook, id: "new-book", title: "New Result", sortTitle: "New Result" }])));
    const { container } = await mount("/groups/group%2Fid/edit?tab=add-books");
    const input = container.querySelector<HTMLInputElement>("#group-add-books-search")!;
    const form = container.querySelector<HTMLFormElement>('form[role="search"]')!;

    await act(async () => setControlValue(input, "Old"));
    await act(async () => submit(form));
    await act(async () => setControlValue(input, "New"));
    await act(async () => submit(form));
    expect(container.textContent).toContain("New Result");

    await act(async () => oldSearch.resolve(page([{ ...candidateBook, id: "old-book", title: "Old Result", sortTitle: "Old Result" }])));
    expect(container.textContent).toContain("New Result");
    expect(container.textContent).not.toContain("Old Result");
  });

  it("does not load or expose mutation controls without Group authority", async () => {
    sdk.getGroup.mockResolvedValue(group);
    const reader = { ...manager, role: "reader", isManager: false, isReader: true } satisfies CurrentUser;
    const { container } = await mount("/groups/group%2Fid/edit?tab=books", reader);

    expect(sdk.listBooks).not.toHaveBeenCalled();
    expect(container.querySelector('[aria-label="Remove Assigned Book from group"]')).toBeNull();
    expect(container.querySelector("[role=\"alert\"]")).not.toBeNull();
  });
});
