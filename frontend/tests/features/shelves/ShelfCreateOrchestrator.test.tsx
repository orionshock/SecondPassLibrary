/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, Outlet, RouterProvider, useLocation } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CurrentUser, ServerInfo } from "@second-pass/spl-api";
import type { AppOutletContext } from "../../../src/app/layout/AppOrchestrator";

const sdk = vi.hoisted(() => ({ createShelf: vi.fn(), listGroups: vi.fn() }));
vi.mock("@second-pass/spl-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@second-pass/spl-api")>()),
  createShelf: sdk.createShelf,
  listAllLibraryGroups: sdk.listGroups,
}));

import { ShelfCreateOrchestrator } from "../../../src/features/shelves/ShelfCreateOrchestrator";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
  vi.clearAllMocks();
});

function Destination() {
  return <div data-destination={useLocation().pathname} />;
}

async function mountCreate() {
  const container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  const currentUser: CurrentUser = { username: "reader", email: "", firstName: "", lastName: "", profileId: "profile", role: "reader", mustChangePassword: false, isOwner: false, isManager: false, isLibrarian: false, isReader: true, canAccessDjangoAdmin: false, groups: [] };
  const serverInfo = { advancedLibraryGroupsEnabled: false } as ServerInfo;
  const context = { currentUser, serverInfo, refreshCurrentUser: vi.fn(), refreshServerInfo: vi.fn(), onCurrentUserChange: vi.fn(), setBreadcrumbs: vi.fn() } satisfies AppOutletContext;
  const router = createMemoryRouter([{
    element: <Outlet context={context} />,
    children: [
      { path: "/shelves/new", element: <ShelfCreateOrchestrator /> },
      { path: "/shelves/:shelfId/edit", element: <Destination /> },
    ],
  }], { initialEntries: ["/shelves/new"] });
  await act(async () => root?.render(<RouterProvider router={router} />));
  return container;
}

function enterName(container: HTMLElement, value: string) {
  const input = container.querySelector<HTMLInputElement>("#shelf-name")!;
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

describe("ShelfCreateOrchestrator", () => {
  it("creates a personal Shelf and navigates to its edit surface", async () => {
    sdk.createShelf.mockResolvedValue({ id: "shelf/id", name: "Favorites", description: "", ownerType: "user", ownerUser: { username: "reader" }, ownerGroup: null, visibility: "private", itemCount: 0, previewBooks: [] });
    const container = await mountCreate();

    await act(async () => enterName(container, "  Favorites  "));
    await act(async () => container.querySelector("form")?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })));

    expect(sdk.createShelf).toHaveBeenCalledWith({ name: "Favorites", description: "", ownerType: "user", visibility: "private" });
    expect(sdk.listGroups).not.toHaveBeenCalled();
    expect(container.querySelector("[data-destination='/shelves/shelf%2Fid/edit']")).not.toBeNull();
  });

  it("preserves the Shelf draft after a failed mutation", async () => {
    sdk.createShelf.mockRejectedValue(new Error("Shelf could not be created."));
    const container = await mountCreate();

    await act(async () => enterName(container, "Favorites"));
    await act(async () => container.querySelector("form")?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })));

    expect(container.querySelector<HTMLInputElement>("#shelf-name")?.value).toBe("Favorites");
    expect(container.textContent).toContain("Shelf could not be created.");
  });
});
