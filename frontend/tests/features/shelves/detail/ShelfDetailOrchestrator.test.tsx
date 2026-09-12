/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, Outlet, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CompactBook, Page, ShelfItem, ShelfSummary } from "@second-pass/spl-api";
import { ShelfDetailOrchestrator } from "../../../../src/features/shelves/detail/ShelfDetailOrchestrator";
import { buttonNamed, deferred } from "../../../support/domInteraction";

const sdk = vi.hoisted(() => ({ getShelf: vi.fn(), listShelfItems: vi.fn() }));
vi.mock("@second-pass/spl-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@second-pass/spl-api")>()),
  getShelf: sdk.getShelf,
  listShelfItems: sdk.listShelfItems,
}));

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const shelf = (id: string, name: string): ShelfSummary => ({
  id, name, description: "", ownerType: "user", ownerUser: { profileId: "reader", username: "reader" }, ownerGroup: null,
  visibility: "private", itemCount: 1, previewBooks: [], canEdit: true,
});
const book = (id: string, title: string): CompactBook => ({
  id, title, sortTitle: title, subtitle: "", authors: [], series: null, catalogTags: [], language: "", publisher: "",
  publishedYear: null, publishedMonth: null, publishedDay: null, publishedDatePrecision: "", coverUrl: null, fileFormat: "epub",
});
const item = (id: string, position: number, value: CompactBook): ShelfItem => ({ id, shelfId: "shelf-one", position, addedBy: null, book: value });
const page = (items: ShelfItem[]): Page<ShelfItem> => ({ items, count: items.length, next: null, previous: null });
let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
  vi.clearAllMocks();
});

function prime() {
  sdk.getShelf.mockResolvedValue(shelf("shelf-one", "Shelf One"));
  sdk.listShelfItems.mockResolvedValue(page([item("item-one", 0, book("book-one", "Book One"))]));
}

async function mount(path = "/shelves/shelf-one") {
  const container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  const router = createMemoryRouter([{ element: <Outlet context={{ setBreadcrumbs: vi.fn() }} />, children: [{ path: "/shelves/:shelfId", element: <ShelfDetailOrchestrator /> }] }], { initialEntries: [path] });
  await act(async () => root?.render(<RouterProvider router={router} />));
  return { container, router };
}

describe("ShelfDetailOrchestrator", () => {
  it("loads the Shelf and its URL-ordered authoritative items", async () => {
    prime();
    const { container } = await mount("/shelves/shelf-one?ordering=-position&page=2&page_size=30");

    expect(sdk.getShelf).toHaveBeenCalledWith("shelf-one");
    expect(sdk.listShelfItems).toHaveBeenCalledWith("shelf-one", { ordering: "-position", page: 2, pageSize: 30 });
    expect(container.querySelector('a[href="/library/books/book-one"]')).not.toBeNull();
    expect(container.querySelector('a[href="/shelves/shelf-one/edit"]')).not.toBeNull();
  });

  it("retries detail and item failures independently", async () => {
    sdk.getShelf.mockRejectedValueOnce(new Error("Shelf unavailable.")).mockResolvedValueOnce(shelf("shelf-one", "Recovered Shelf"));
    sdk.listShelfItems.mockRejectedValueOnce(new Error("Items unavailable.")).mockResolvedValueOnce(page([item("recovered", 0, book("recovered", "Recovered Book"))]));
    const { container } = await mount();

    await act(async () => buttonNamed(container, "Retry").click());
    expect(container.textContent).toContain("Items unavailable.");
    await act(async () => buttonNamed(container, "Retry").click());

    expect(sdk.getShelf).toHaveBeenCalledTimes(2);
    expect(sdk.listShelfItems).toHaveBeenCalledTimes(2);
    expect(container.querySelector('a[href="/library/books/recovered"]')).not.toBeNull();
  });

  it("replaces item ordering without reloading Shelf identity", async () => {
    prime();
    const { container } = await mount();
    const ordering = container.querySelector<HTMLButtonElement>('button[aria-label^="Order shelf books"]')!;
    await act(async () => ordering.click());
    const titleOrder = Array.from(container.querySelectorAll<HTMLButtonElement>('[role="menuitemradio"]'))
      .find((button) => button.textContent?.includes("Title A-Z"));
    expect(titleOrder).toBeDefined();
    await act(async () => titleOrder?.click());

    expect(sdk.getShelf).toHaveBeenCalledOnce();
    expect(sdk.listShelfItems).toHaveBeenLastCalledWith("shelf-one", { ordering: "title", page: 1, pageSize: 20 });
  });

  it("does not let the previous route identity replace the current Shelf", async () => {
    const oldRequest = deferred<ShelfSummary>();
    const newRequest = deferred<ShelfSummary>();
    sdk.getShelf.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise);
    sdk.listShelfItems.mockResolvedValue(page([]));
    const { container, router } = await mount();

    await act(async () => router.navigate("/shelves/shelf-two"));
    expect(sdk.getShelf).toHaveBeenLastCalledWith("shelf-two");
    await act(async () => newRequest.resolve(shelf("shelf-two", "Shelf Two")));
    await act(async () => oldRequest.resolve(shelf("shelf-one", "Shelf One")));

    expect(container.textContent).toContain("Shelf Two");
    expect(container.textContent).not.toContain("Shelf One");
  });
});
