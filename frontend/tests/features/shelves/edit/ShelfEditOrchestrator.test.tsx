/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, Outlet, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, type CompactBook, type CurrentUser, type ServerInfo, type ShelfEditorItem, type ShelfEditorItemsPage, type ShelfSummary } from "@second-pass/spl-api";
import type { AppOutletContext } from "../../../../src/app/layout/AppOrchestrator";
import { ShelfEditOrchestrator } from "../../../../src/features/shelves/edit/ShelfEditOrchestrator";
import { buttonNamed, deferred, setControlValue, submit } from "../../../support/domInteraction";

const sdk = vi.hoisted(() => ({
  getShelf: vi.fn(), updateShelf: vi.fn(), deleteShelf: vi.fn(),
  listItems: vi.fn(), addItem: vi.fn(), removeItem: vi.fn(), moveItem: vi.fn(), setPosition: vi.fn(),
  searchLibrary: vi.fn(), searchGroup: vi.fn(),
}));
vi.mock("@second-pass/spl-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@second-pass/spl-api")>()),
  getShelf: sdk.getShelf,
  updateShelf: sdk.updateShelf,
  deleteShelf: sdk.deleteShelf,
  listShelfEditorItems: sdk.listItems,
  addShelfItem: sdk.addItem,
  removeShelfItem: sdk.removeItem,
  moveShelfItem: sdk.moveItem,
  setShelfItemPosition: sdk.setPosition,
  searchLibraryBooks: sdk.searchLibrary,
  searchGroupBooks: sdk.searchGroup,
}));

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const shelf: ShelfSummary = {
  id: "shelf/id", name: "Favorites", description: "<p>Original description</p>", ownerType: "user",
  ownerUser: { profileId: "profile", username: "reader" }, ownerGroup: null,
  visibility: "listed", itemCount: 2, canEdit: true,
};
const book = (id: string, title: string): CompactBook => ({
  id, title, sortTitle: title, subtitle: "", authors: [], series: null, catalogTags: [], language: "",
  publisher: "", publishedYear: null, publishedMonth: null, publishedDay: null,
  publishedDatePrecision: "", coverUrl: null, fileFormat: "epub",
});
const item = (id: string, position: number, title: string): ShelfEditorItem => ({
  id, shelfId: shelf.id, position, unavailable: false, addedBy: null, book: book(`book-${id}`, title),
});
const first = item("one", 0, "Book One");
const second = item("two", 1, "Book Two");
const itemPage = (items: ShelfEditorItem[]): ShelfEditorItemsPage => ({
  items, count: items.length, visibleItemCount: items.length, unavailableItemCount: 0,
  next: null, previous: null,
});
const currentUser = {
  username: "reader", email: "", firstName: "", lastName: "", profileId: "profile",
  role: "reader", mustChangePassword: false, isOwner: false, isManager: false,
  isLibrarian: false, isReader: true, canAccessDjangoAdmin: false, groups: [],
} satisfies CurrentUser;
const serverInfo = {
  serverId: "server-id", serverUrls: [],
  name: "Library", description: "", bannerText: "", advancedLibraryGroupsEnabled: true,
  secondPassReaderWebClientUrl: null, marginaliaProfileUri: "profile", version: "dev",
  releaseDate: "", publicGroup: { id: "public", name: "Common Room", description: "" },
} satisfies ServerInfo;
let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

function arrangeDependencies() {
  sdk.getShelf.mockResolvedValue(shelf);
  sdk.listItems.mockResolvedValue(itemPage([first, second]));
  sdk.searchLibrary.mockResolvedValue({ items: [], count: 0, next: null, previous: null });
}

async function mount(path = "/shelves/shelf%2Fid/edit") {
  const container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  const context = {
    currentUser, serverInfo, refreshCurrentUser: vi.fn(), refreshServerInfo: vi.fn(),
    onCurrentUserChange: vi.fn(), setBreadcrumbs: vi.fn(),
  } satisfies AppOutletContext;
  const router = createMemoryRouter([{
    element: <Outlet context={context} />,
    children: [
      { path: "/shelves/:shelfId/edit", element: <ShelfEditOrchestrator /> },
      { path: "/shelves", element: <div data-testid="shelves-list" /> },
    ],
  }], { initialEntries: [path] });
  await act(async () => root?.render(<RouterProvider router={router} />));
  return { container, router };
}

async function setDescription(container: HTMLElement, value: string) {
  await act(async () => buttonNamed(container, "Show raw").click());
  await act(async () => setControlValue(container.querySelector<HTMLTextAreaElement>("textarea#shelf-description")!, value));
}

describe("ShelfEditOrchestrator metadata and deletion", () => {
  it("loads and saves rich Shelf metadata while preventing duplicate submission", async () => {
    arrangeDependencies();
    const pending = deferred<ShelfSummary>();
    sdk.updateShelf.mockReturnValue(pending.promise);
    const { container } = await mount();

    expect(sdk.getShelf).toHaveBeenCalledWith("shelf/id");
    await setDescription(container, "<p>Edited <strong>description</strong></p>");
    act(() => submit(container.querySelector("form")!));

    expect(sdk.updateShelf).toHaveBeenCalledWith("shelf/id", {
      name: "Favorites", description: "<p>Edited <strong>description</strong></p>", visibility: "listed",
    });
    expect(container.querySelector<HTMLButtonElement>('button[type="submit"]')?.disabled).toBe(true);
    const nameInput = container.querySelector<HTMLInputElement>("#shelf-name")!;
    expect(nameInput.disabled).toBe(true);
    await act(async () => setControlValue(nameInput, "Newer Shelf"));
    expect(nameInput.value).toBe("Favorites");
    act(() => submit(container.querySelector("form")!));
    buttonNamed(container, "Saving...").click();
    expect(sdk.updateShelf).toHaveBeenCalledOnce();

    await act(async () => pending.resolve({ ...shelf, description: "<p>Saved description</p>" }));
    expect(container.querySelector<HTMLTextAreaElement>("textarea#shelf-description")?.value).toBe("<p>Saved description</p>");
    expect(container.querySelector<HTMLInputElement>("#shelf-name")?.disabled).toBe(false);
  });

  it("keeps the edited Shelf draft after save failure", async () => {
    arrangeDependencies();
    const failedSave = deferred<ShelfSummary>();
    sdk.updateShelf.mockReturnValueOnce(failedSave.promise).mockResolvedValueOnce({ ...shelf, name: "Unsaved Shelf" });
    const { container } = await mount();

    await act(async () => setControlValue(container.querySelector<HTMLInputElement>("#shelf-name")!, "Unsaved Shelf"));
    act(() => submit(container.querySelector("form")!));
    expect(container.querySelector<HTMLInputElement>("#shelf-name")?.disabled).toBe(true);
    await act(async () => failedSave.reject(new Error("Shelf save failed.")));

    expect(container.querySelector<HTMLInputElement>("#shelf-name")?.value).toBe("Unsaved Shelf");
    expect(container.querySelector<HTMLInputElement>("#shelf-name")?.disabled).toBe(false);
    expect(container.querySelector("[role=\"alert\"]")).not.toBeNull();
    await act(async () => submit(container.querySelector("form")!));
    expect(sdk.updateShelf).toHaveBeenCalledTimes(2);
  });

  it("deletes only after confirmation and navigates after server success", async () => {
    arrangeDependencies();
    const pending = deferred<void>();
    sdk.deleteShelf.mockReturnValue(pending.promise);
    const confirm = vi.fn(() => false);
    vi.stubGlobal("confirm", confirm);
    const { container, router } = await mount();

    await act(async () => buttonNamed(container, "Delete Shelf").click());
    expect(sdk.deleteShelf).not.toHaveBeenCalled();
    confirm.mockReturnValue(true);
    act(() => buttonNamed(container, "Delete Shelf").click());

    expect(sdk.deleteShelf).toHaveBeenCalledWith("shelf/id");
    expect(buttonNamed(container, "Deleting...").disabled).toBe(true);
    expect(router.state.location.pathname).toContain("/shelves/shelf%2Fid/edit");
    await act(async () => pending.resolve());
    expect(router.state.location.pathname).toBe("/shelves");
  });

  it("remains on the Shelf and keeps its state when deletion fails", async () => {
    arrangeDependencies();
    sdk.deleteShelf.mockRejectedValue(new Error("Shelf delete failed."));
    vi.stubGlobal("confirm", vi.fn(() => true));
    const { container, router } = await mount();

    await act(async () => buttonNamed(container, "Delete Shelf").click());

    expect(router.state.location.pathname).toContain("/shelves/shelf%2Fid/edit");
    expect(container.querySelector<HTMLInputElement>("#shelf-name")?.value).toBe("Favorites");
    expect(container.querySelector("[role=\"alert\"]")).not.toBeNull();
  });
});

describe("ShelfEditOrchestrator item mutations", () => {
  it("moves an item, locks conflicting commands, and reloads authoritative order", async () => {
    arrangeDependencies();
    sdk.listItems.mockResolvedValueOnce(itemPage([first, second])).mockResolvedValueOnce(itemPage([
      { ...second, position: 0 }, { ...first, position: 1 },
    ]));
    const pending = deferred<void>();
    sdk.moveItem.mockReturnValue(pending.promise);
    const { container } = await mount("/shelves/shelf%2Fid/edit?tab=books");

    act(() => buttonNamed(container, "Move Book One down").click());
    expect(sdk.moveItem).toHaveBeenCalledWith("shelf/id", "one", "down");
    expect(buttonNamed(container, "Move Book Two up").disabled).toBe(true);
    await act(async () => pending.resolve());

    expect(sdk.listItems).toHaveBeenCalledTimes(2);
    expect(container.textContent?.indexOf("Book Two")).toBeLessThan(container.textContent?.indexOf("Book One") ?? 0);
  });

  it("preserves authoritative order when a move fails", async () => {
    arrangeDependencies();
    sdk.moveItem.mockRejectedValue(new Error("Move failed."));
    const { container } = await mount("/shelves/shelf%2Fid/edit?tab=books");

    await act(async () => buttonNamed(container, "Move Book One down").click());

    expect(container.textContent?.indexOf("Book One")).toBeLessThan(container.textContent?.indexOf("Book Two") ?? 0);
    expect(sdk.listItems).toHaveBeenCalledOnce();
    expect(container.querySelector("[role=\"alert\"]")).not.toBeNull();
  });

  it("sends an upward move through the same ordered-item mutation boundary", async () => {
    arrangeDependencies();
    sdk.moveItem.mockResolvedValue(undefined);
    const { container } = await mount("/shelves/shelf%2Fid/edit?tab=books");

    await act(async () => buttonNamed(container, "Move Book Two up").click());

    expect(sdk.moveItem).toHaveBeenCalledWith("shelf/id", "two", "up");
    expect(sdk.getShelf).toHaveBeenCalledTimes(2);
  });

  it("adds a Book and refreshes candidates plus the Shelf summary", async () => {
    arrangeDependencies();
    const candidate = book("candidate", "Candidate Book");
    sdk.searchLibrary.mockResolvedValueOnce({ items: [candidate], count: 1, next: null, previous: null })
      .mockResolvedValueOnce({ items: [], count: 0, next: null, previous: null });
    sdk.addItem.mockResolvedValue(undefined);
    const { container } = await mount("/shelves/shelf%2Fid/edit?tab=add-books&q=Candidate");

    await act(async () => buttonNamed(container, "Add").click());

    expect(sdk.addItem).toHaveBeenCalledWith("shelf/id", { bookId: "candidate" });
    expect(sdk.getShelf).toHaveBeenCalledTimes(2);
    expect(sdk.searchLibrary).toHaveBeenCalledTimes(2);
    expect(container.textContent).not.toContain("Candidate Book");
  });

  it("recovers candidate search URL state after adding the sole final-page result", async () => {
    arrangeDependencies();
    const candidate = book("candidate", "Candidate Book");
    const recovered = { items: [], count: 30, next: null, previous: null };
    sdk.searchLibrary
      .mockResolvedValueOnce({ items: [candidate], count: 31, next: null, previous: "page-1" })
      .mockRejectedValueOnce(new ApiError("Invalid page.", 404))
      .mockResolvedValue(recovered);
    sdk.addItem.mockResolvedValue(undefined);
    const { container, router } = await mount(
      "/shelves/shelf%2Fid/edit?tab=add-books&q=Candidate&page=2&page_size=30",
    );

    await act(async () => buttonNamed(container, "Add").click());

    expect(sdk.searchLibrary.mock.calls.map(([query]) => query.page)).toEqual([2, 2, 1, 1]);
    expect(router.state.location.search).toBe("?tab=add-books&page_size=30&q=Candidate");
    expect(router.state.historyAction).toBe("REPLACE");
    expect(container.querySelector("[role=\"alert\"]")).toBeNull();
  });

  it("keeps a candidate visible when adding it fails", async () => {
    arrangeDependencies();
    const candidate = book("candidate", "Candidate Book");
    sdk.searchLibrary.mockResolvedValue({ items: [candidate], count: 1, next: null, previous: null });
    sdk.addItem.mockRejectedValue(new Error("Add failed."));
    const { container } = await mount("/shelves/shelf%2Fid/edit?tab=add-books&q=Candidate");

    await act(async () => buttonNamed(container, "Add").click());

    expect(container.textContent).toContain("Candidate Book");
    expect(sdk.getShelf).toHaveBeenCalledOnce();
    expect(container.querySelector("[role=\"alert\"]")).not.toBeNull();
  });

  it("removes a Book and refreshes items plus the Shelf summary after success", async () => {
    arrangeDependencies();
    sdk.listItems.mockResolvedValueOnce(itemPage([first, second])).mockResolvedValueOnce(itemPage([second]));
    sdk.removeItem.mockResolvedValue(undefined);
    const { container } = await mount("/shelves/shelf%2Fid/edit?tab=books");

    await act(async () => buttonNamed(container, "Remove Book One from shelf").click());

    expect(sdk.removeItem).toHaveBeenCalledWith("shelf/id", "one");
    expect(sdk.listItems).toHaveBeenCalledTimes(2);
    expect(sdk.getShelf).toHaveBeenCalledTimes(2);
    expect(container.querySelector('[aria-label="Remove Book One from shelf"]')).toBeNull();
  });

  it("recovers to the last valid URL page after removing the sole final-page item", async () => {
    arrangeDependencies();
    sdk.listItems
      .mockResolvedValueOnce({ ...itemPage([first]), count: 31, previous: "page-1" })
      .mockRejectedValueOnce(new ApiError("Invalid page.", 404))
      .mockResolvedValue({ ...itemPage([second]), count: 30 });
    sdk.removeItem.mockResolvedValue(undefined);
    const { container, router } = await mount(
      "/shelves/shelf%2Fid/edit?tab=books&page=2&page_size=30",
    );

    await act(async () => buttonNamed(container, "Remove Book One from shelf").click());

    expect(sdk.listItems.mock.calls.map(([, query]) => query.page)).toEqual([2, 2, 1, 1]);
    expect(router.state.location.search).toBe("?tab=books&page_size=30");
    expect(router.state.historyAction).toBe("REPLACE");
    expect(container.textContent).toContain("Book Two");
    expect(container.querySelector("[role=\"alert\"]")).toBeNull();
  });

  it("removes a Book and does not hide it when removal fails", async () => {
    arrangeDependencies();
    sdk.removeItem.mockRejectedValue(new Error("Remove failed."));
    const { container } = await mount("/shelves/shelf%2Fid/edit?tab=books");

    await act(async () => buttonNamed(container, "Remove Book One from shelf").click());

    expect(sdk.removeItem).toHaveBeenCalledWith("shelf/id", "one");
    expect(container.textContent).toContain("Book One");
    expect(sdk.getShelf).toHaveBeenCalledOnce();
    expect(container.querySelector("[role=\"alert\"]")).not.toBeNull();
  });
});
