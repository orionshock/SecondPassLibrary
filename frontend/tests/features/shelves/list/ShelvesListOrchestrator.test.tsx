/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, Outlet, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Page, ShelfSummary } from "@second-pass/spl-api";
import { ShelvesListOrchestrator } from "../../../../src/features/shelves/list/ShelvesListOrchestrator";
import { buttonNamed, deferred } from "../../../support/domInteraction";

const sdk = vi.hoisted(() => ({ listShelves: vi.fn() }));
vi.mock("@second-pass/spl-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@second-pass/spl-api")>()),
  listShelves: sdk.listShelves,
}));

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const shelf = (id: string, name: string): ShelfSummary => ({
  id, name, description: "", ownerType: "user", ownerUser: { profileId: "reader", username: "reader" }, ownerGroup: null,
  visibility: "private", itemCount: 1, previewBooks: [], canEdit: true,
});
const page = (items: ShelfSummary[]): Page<ShelfSummary> => ({ items, count: items.length, next: null, previous: null });
let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
  vi.clearAllMocks();
});

async function mount(path = "/shelves") {
  const container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  const router = createMemoryRouter([{ element: <Outlet context={{ setBreadcrumbs: vi.fn() }} />, children: [{ path: "/shelves", element: <ShelvesListOrchestrator /> }] }], { initialEntries: [path] });
  await act(async () => root?.render(<RouterProvider router={router} />));
  return { container, router };
}

describe("ShelvesListOrchestrator", () => {
  it("loads URL-backed scope and ordering and replaces them from the controls", async () => {
    sdk.listShelves.mockResolvedValue(page([shelf("shared", "Shared Shelf")]));
    const { container } = await mount("/shelves?scope=shared&ordering=-item_count&page=2&page_size=30");

    expect(sdk.listShelves).toHaveBeenCalledWith({ scope: "shared", ordering: "-item_count", includePreviewBooks: true, previewLimit: 12, page: 2, pageSize: 30 });
    expect(container.querySelector('a[href="/shelves/shared"]')).not.toBeNull();

    const groupScope = Array.from(container.querySelectorAll<HTMLButtonElement>('[role="group"][aria-label="Shelf scopes"] button'))
      .find((button) => button.textContent?.includes("Group Shelves"));
    expect(groupScope).toBeDefined();
    await act(async () => groupScope?.click());
    expect(sdk.listShelves).toHaveBeenLastCalledWith(expect.objectContaining({ scope: "group", page: 1 }));
  });

  it("retries a failed Shelf request", async () => {
    sdk.listShelves.mockRejectedValueOnce(new Error("Shelves unavailable.")).mockResolvedValueOnce(page([shelf("recovered", "Recovered Shelf")]));
    const { container } = await mount();

    await act(async () => buttonNamed(container, "Retry").click());

    expect(sdk.listShelves).toHaveBeenCalledTimes(2);
    expect(container.querySelector('a[href="/shelves/recovered"]')).not.toBeNull();
  });

  it("does not allow an old scope result to replace newer Shelves", async () => {
    const personal = deferred<Page<ShelfSummary>>();
    const group = deferred<Page<ShelfSummary>>();
    sdk.listShelves.mockReturnValueOnce(personal.promise).mockReturnValueOnce(group.promise);
    const { container, router } = await mount();

    await act(async () => router.navigate("/shelves?scope=group"));
    await act(async () => group.resolve(page([shelf("group", "Group Shelf")])));
    await act(async () => personal.resolve(page([shelf("personal", "Personal Shelf")])));

    expect(container.querySelector('a[href="/shelves/group"]')).not.toBeNull();
    expect(container.querySelector('a[href="/shelves/personal"]')).toBeNull();
  });
});
