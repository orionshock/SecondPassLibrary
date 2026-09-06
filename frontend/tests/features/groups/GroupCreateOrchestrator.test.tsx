/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, Outlet, RouterProvider, useLocation } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CurrentUser, ServerInfo } from "@second-pass/spl-api";
import type { AppOutletContext } from "../../../src/app/layout/AppOrchestrator";

const sdk = vi.hoisted(() => ({ createGroup: vi.fn() }));
vi.mock("@second-pass/spl-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@second-pass/spl-api")>()),
  createGroup: sdk.createGroup,
}));

import { GroupCreateOrchestrator } from "../../../src/features/groups/GroupCreateOrchestrator";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
  vi.clearAllMocks();
});

function Destination() {
  const location = useLocation();
  return <div data-destination={location.pathname} />;
}

async function mountCreate() {
  const container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  const currentUser: CurrentUser = { username: "manager", email: "", firstName: "", lastName: "", profileId: "profile", role: "manager", mustChangePassword: false, isOwner: false, isManager: true, isLibrarian: false, isReader: false, canAccessDjangoAdmin: false, groups: [] };
  const serverInfo = { advancedLibraryGroupsEnabled: true } as ServerInfo;
  const context = { currentUser, serverInfo, refreshCurrentUser: vi.fn(), refreshServerInfo: vi.fn(), onCurrentUserChange: vi.fn(), setBreadcrumbs: vi.fn() } satisfies AppOutletContext;
  const router = createMemoryRouter([{
    element: <Outlet context={context} />,
    children: [
      { path: "/groups/new", element: <GroupCreateOrchestrator /> },
      { path: "/groups/:groupId/edit", element: <Destination /> },
    ],
  }], { initialEntries: ["/groups/new"] });
  await act(async () => root?.render(<RouterProvider router={router} />));
  return container;
}

function enterName(container: HTMLElement, value: string) {
  const input = container.querySelector<HTMLInputElement>("#group-name")!;
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

describe("GroupCreateOrchestrator", () => {
  it("submits the normalized draft and navigates to the saved Group", async () => {
    sdk.createGroup.mockResolvedValue({ id: "group/id", name: "Readers", description: "", isPublicGroup: false });
    const container = await mountCreate();

    await act(async () => enterName(container, "  Readers  "));
    await act(async () => container.querySelector("form")?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })));

    expect(sdk.createGroup).toHaveBeenCalledWith({ name: "Readers", description: "" });
    expect(container.querySelector("[data-destination='/groups/group%2Fid/edit']")).not.toBeNull();
  });

  it("retains the draft and displays a failed create mutation", async () => {
    sdk.createGroup.mockRejectedValue(new Error("Group could not be created."));
    const container = await mountCreate();

    await act(async () => enterName(container, "Readers"));
    await act(async () => container.querySelector("form")?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })));

    expect(container.querySelector<HTMLInputElement>("#group-name")?.value).toBe("Readers");
    expect(container.textContent).toContain("Group could not be created.");
  });
});
